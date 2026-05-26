"""Tests for the database storage layer."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from form_crawler.storage.database import Database
from form_crawler.storage.models import Company, FormData


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.mark.asyncio
async def test_create_and_fetch_company(db_path):
    async with Database(db_path) as db:
        company = Company(
            name="Test Corp",
            site="https://testcorp.ru",
            category="застройщики",
            city="Москва",
        )
        cid = await db.insert_company(company)
        assert cid > 0

        fetched = await db.get_company_by_site("https://testcorp.ru")
        assert fetched is not None
        assert fetched.name == "Test Corp"
        assert fetched.category == "застройщики"


@pytest.mark.asyncio
async def test_insert_duplicate_company(db_path):
    async with Database(db_path) as db:
        c1 = Company(name="Corp", site="https://corp.ru", category="мебель")
        c2 = Company(name="Corp Updated", site="https://corp.ru", category="окна")

        id1 = await db.insert_company(c1)
        id2 = await db.insert_company(c2)
        assert id1 == id2  # same site = same record


@pytest.mark.asyncio
async def test_update_company(db_path):
    async with Database(db_path) as db:
        company = Company(name="Test", site="https://test.ru", category="услуги")
        cid = await db.insert_company(company)

        await db.update_company(cid, status="crawled", cms="bitrix")

        fetched = await db.get_company_by_site("https://test.ru")
        assert fetched.status == "crawled"
        assert fetched.cms == "bitrix"


@pytest.mark.asyncio
async def test_insert_and_fetch_form(db_path):
    async with Database(db_path) as db:
        company = Company(name="Test", site="https://test.ru", category="окна")
        cid = await db.insert_company(company)

        form = FormData(
            company_id=cid,
            page_url="https://test.ru/contacts",
            form_type="callback",
            action="/ajax/callback",
            method="POST",
            submit_type="ajax",
            endpoint="/ajax/callback",
            captcha="none",
        )
        fid = await db.insert_form(form)
        assert fid > 0

        forms = await db.get_forms_by_company(cid)
        assert len(forms) == 1
        assert forms[0].form_type == "callback"
        assert forms[0].endpoint == "/ajax/callback"


@pytest.mark.asyncio
async def test_get_pending_companies(db_path):
    async with Database(db_path) as db:
        for i in range(5):
            c = Company(name=f"Corp{i}", site=f"https://corp{i}.ru", category="ремонт")
            await db.insert_company(c)

        # Update 2 as crawled
        await db.update_company(1, status="crawled")
        await db.update_company(2, status="crawled")

        pending = await db.get_pending_companies()
        assert len(pending) == 3


@pytest.mark.asyncio
async def test_counts(db_path):
    async with Database(db_path) as db:
        for i in range(3):
            c = Company(name=f"C{i}", site=f"https://c{i}.ru", category="B2B компании")
            cid = await db.insert_company(c)
            f = FormData(company_id=cid, page_url=f"https://c{i}.ru/", form_type="contact")
            await db.insert_form(f)

        assert await db.count_companies() == 3
        assert await db.count_forms() == 3
