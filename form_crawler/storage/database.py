"""SQLite database layer with async support via aiosqlite."""

import json
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from .models import Company, FormData


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    site TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT '',
    city TEXT DEFAULT '',
    cms TEXT DEFAULT '',
    libraries TEXT DEFAULT '[]',
    antibot TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    page_url TEXT NOT NULL,
    form_type TEXT DEFAULT '',
    html TEXT DEFAULT '',
    action TEXT DEFAULT '',
    method TEXT DEFAULT '',
    submit_type TEXT DEFAULT '',
    endpoint TEXT DEFAULT '',
    fields TEXT DEFAULT '[]',
    hidden_fields TEXT DEFAULT '[]',
    csrf_token TEXT DEFAULT '',
    captcha TEXT DEFAULT 'none',
    selectors TEXT DEFAULT '{}',
    xpath TEXT DEFAULT '',
    js_events TEXT DEFAULT '[]',
    iframe_src TEXT DEFAULT '',
    shadow_dom INTEGER DEFAULT 0,
    is_modal INTEGER DEFAULT 0,
    trigger_selector TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_companies_site ON companies(site);
CREATE INDEX IF NOT EXISTS idx_companies_category ON companies(category);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_forms_company_id ON forms(company_id);
CREATE INDEX IF NOT EXISTS idx_forms_form_type ON forms(form_type);
"""


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Open connection and initialize schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self):
        """Close connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Companies ──

    async def insert_company(self, company: Company) -> int:
        """Insert or ignore a company. Returns id."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """INSERT OR IGNORE INTO companies 
               (name, site, category, city, cms, libraries, antibot, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company.name,
                company.site,
                company.category,
                company.city,
                company.cms,
                company.libraries,
                company.antibot,
                company.status,
                now,
                now,
            ),
        ) as cursor:
            await self._conn.commit()
            if cursor.lastrowid:
                return cursor.lastrowid

        # If INSERT OR IGNORE hit a duplicate, fetch existing id
        async with self._conn.execute(
            "SELECT id FROM companies WHERE site = ?", (company.site,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_company(self, company_id: int, **kwargs):
        """Update company fields."""
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [company_id]
        await self._conn.execute(
            f"UPDATE companies SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    async def get_company_by_site(self, site: str) -> Optional[Company]:
        """Fetch company by site URL."""
        async with self._conn.execute(
            "SELECT * FROM companies WHERE site = ?", (site,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_company(row)
        return None

    async def get_pending_companies(self, limit: int = 100) -> list[Company]:
        """Get companies that haven't been crawled yet."""
        async with self._conn.execute(
            "SELECT * FROM companies WHERE status = 'pending' LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_company(r) for r in rows]

    async def get_all_companies(self) -> list[Company]:
        """Get all companies."""
        async with self._conn.execute("SELECT * FROM companies ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_company(r) for r in rows]

    async def count_companies(self) -> int:
        async with self._conn.execute("SELECT COUNT(*) FROM companies") as cursor:
            row = await cursor.fetchone()
            return row[0]

    # ── Forms ──

    async def insert_form(self, form: FormData) -> int:
        """Insert a form record."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            """INSERT INTO forms
               (company_id, page_url, form_type, html, action, method, submit_type,
                endpoint, fields, hidden_fields, csrf_token, captcha, selectors,
                xpath, js_events, iframe_src, shadow_dom, is_modal, trigger_selector, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                form.company_id,
                form.page_url,
                form.form_type,
                form.html,
                form.action,
                form.method,
                form.submit_type,
                form.endpoint,
                form.fields,
                form.hidden_fields,
                form.csrf_token,
                form.captcha,
                form.selectors,
                form.xpath,
                form.js_events,
                form.iframe_src,
                int(form.shadow_dom),
                int(form.is_modal),
                form.trigger_selector,
                now,
            ),
        ) as cursor:
            await self._conn.commit()
            return cursor.lastrowid

    async def get_forms_by_company(self, company_id: int) -> list[FormData]:
        """Get all forms for a company."""
        async with self._conn.execute(
            "SELECT * FROM forms WHERE company_id = ? ORDER BY id", (company_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_form(r) for r in rows]

    async def get_all_forms(self) -> list[FormData]:
        """Get all forms."""
        async with self._conn.execute("SELECT * FROM forms ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_form(r) for r in rows]

    async def count_forms(self) -> int:
        async with self._conn.execute("SELECT COUNT(*) FROM forms") as cursor:
            row = await cursor.fetchone()
            return row[0]

    # ── Helpers ──

    @staticmethod
    def _row_to_company(row) -> Company:
        return Company(
            id=row["id"],
            name=row["name"],
            site=row["site"],
            category=row["category"],
            city=row["city"],
            cms=row["cms"],
            libraries=row["libraries"],
            antibot=row["antibot"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_form(row) -> FormData:
        return FormData(
            id=row["id"],
            company_id=row["company_id"],
            page_url=row["page_url"],
            form_type=row["form_type"],
            html=row["html"],
            action=row["action"],
            method=row["method"],
            submit_type=row["submit_type"],
            endpoint=row["endpoint"],
            fields=row["fields"],
            hidden_fields=row["hidden_fields"],
            csrf_token=row["csrf_token"],
            captcha=row["captcha"],
            selectors=row["selectors"],
            xpath=row["xpath"],
            js_events=row["js_events"],
            iframe_src=row["iframe_src"],
            shadow_dom=bool(row["shadow_dom"]),
            is_modal=bool(row["is_modal"]),
            trigger_selector=row["trigger_selector"],
            created_at=row["created_at"],
        )
