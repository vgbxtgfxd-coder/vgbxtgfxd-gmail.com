"""Export data to CSV, XLSX, and JSON formats."""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd

from ..storage.database import Database

logger = logging.getLogger(__name__)



class Exporter:
    """Exports crawl results to various formats."""

    def __init__(self, db: Database, export_dir: Path):
        self.db = db
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    async def export_csv(self, filename: Optional[str] = None) -> Path:
        """Export all data to CSV files."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"forms_export_{ts}"

        # Export companies
        companies = await self.db.get_all_companies()
        companies_path = self.export_dir / f"{fname}_companies.csv"
        with open(companies_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "name", "site", "category", "city", "cms",
                "libraries", "antibot", "status", "created_at",
            ])
            writer.writeheader()
            for c in companies:
                writer.writerow({
                    "id": c.id, "name": c.name, "site": c.site,
                    "category": c.category, "city": c.city, "cms": c.cms,
                    "libraries": c.libraries, "antibot": c.antibot,
                    "status": c.status, "created_at": c.created_at,
                })

        # Export forms
        forms = await self.db.get_all_forms()
        forms_path = self.export_dir / f"{fname}_forms.csv"
        with open(forms_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "company_id", "page_url", "form_type", "action",
                "method", "submit_type", "endpoint", "captcha",
                "is_modal", "trigger_selector", "csrf_token",
                "fields", "hidden_fields", "selectors", "xpath",
            ])
            writer.writeheader()
            for form in forms:
                writer.writerow({
                    "id": form.id, "company_id": form.company_id,
                    "page_url": form.page_url, "form_type": form.form_type,
                    "action": form.action, "method": form.method,
                    "submit_type": form.submit_type, "endpoint": form.endpoint,
                    "captcha": form.captcha, "is_modal": form.is_modal,
                    "trigger_selector": form.trigger_selector,
                    "csrf_token": form.csrf_token,
                    "fields": form.fields, "hidden_fields": form.hidden_fields,
                    "selectors": form.selectors, "xpath": form.xpath,
                })

        logger.info(f"CSV exported: {companies_path}, {forms_path}")
        return companies_path


    async def export_xlsx(self, filename: Optional[str] = None) -> Path:
        """Export all data to Excel file with multiple sheets."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"forms_export_{ts}"
        xlsx_path = self.export_dir / f"{fname}.xlsx"

        companies = await self.db.get_all_companies()
        forms = await self.db.get_all_forms()

        # Build DataFrames
        companies_df = pd.DataFrame([c.to_dict() for c in companies])
        forms_df = pd.DataFrame([f.to_dict() for f in forms])

        # Write to Excel
        with pd.ExcelWriter(str(xlsx_path), engine="openpyxl") as writer:
            if not companies_df.empty:
                companies_df.to_excel(writer, sheet_name="Companies", index=False)
            if not forms_df.empty:
                forms_df.to_excel(writer, sheet_name="Forms", index=False)

        logger.info(f"XLSX exported: {xlsx_path}")
        return xlsx_path

    async def export_json(self, filename: Optional[str] = None) -> Path:
        """Export all data to a single JSON file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"forms_export_{ts}"
        json_path = self.export_dir / f"{fname}.json"

        companies = await self.db.get_all_companies()
        forms = await self.db.get_all_forms()

        # Build nested structure
        data = {
            "exported_at": datetime.now().isoformat(),
            "total_companies": len(companies),
            "total_forms": len(forms),
            "companies": [],
        }

        company_forms_map: dict[int, list] = {}
        for form in forms:
            company_forms_map.setdefault(form.company_id, []).append(form)

        for company in companies:
            company_dict = company.to_dict()
            company_dict["forms"] = [
                f.to_dict() for f in company_forms_map.get(company.id, [])
            ]
            # Parse JSON strings for readability
            for form_dict in company_dict["forms"]:
                for key in ("fields", "hidden_fields", "selectors", "js_events"):
                    val = form_dict.get(key, "")
                    if isinstance(val, str) and val:
                        try:
                            form_dict[key] = json.loads(val)
                        except json.JSONDecodeError:
                            pass
            data["companies"].append(company_dict)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON exported: {json_path}")
        return json_path

    async def export_all(self, filename: Optional[str] = None) -> dict[str, Path]:
        """Export to all supported formats."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"forms_export_{ts}"

        paths = {}
        paths["csv"] = await self.export_csv(fname)
        paths["xlsx"] = await self.export_xlsx(fname)
        paths["json"] = await self.export_json(fname)

        return paths
