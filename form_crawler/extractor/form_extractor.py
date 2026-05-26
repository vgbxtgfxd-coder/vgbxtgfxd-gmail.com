"""Deep form extractor - AJAX endpoints, JS event handlers, full metadata."""

import re
import json
import logging
from typing import Optional
from urllib.parse import urljoin

from ..parser.html_parser import FormParser
from ..crawler.browser import PageResult
from ..storage.models import FormData

logger = logging.getLogger(__name__)



class FormExtractor:
    """Extracts complete form metadata from crawled page results.

    Combines HTML parsing with JS analysis to build complete FormData objects.
    """

    def __init__(self):
        self.parser = FormParser()

    def extract_forms(self, page_result: PageResult, company_id: int) -> list[FormData]:
        """Extract all forms from a page result into FormData objects."""
        forms = []

        # Process forms found by the browser crawler (includes modal forms)
        for raw_form in page_result.forms_html:
            form_data = self._process_raw_form(
                raw_form, page_result, company_id
            )
            if form_data:
                forms.append(form_data)

        # Also parse the full page HTML for forms the crawler might have missed
        if page_result.html:
            page_forms = self.parser.parse_page(page_result.html, page_result.url)
            for pf in page_forms:
                # Avoid duplicates by checking action+method
                if not self._is_duplicate(pf, forms):
                    form_data = self._parsed_to_form_data(
                        pf, page_result, company_id, is_modal=False, trigger=""
                    )
                    if form_data:
                        forms.append(form_data)

        return forms


    def _process_raw_form(
        self, raw_form: dict, page_result: PageResult, company_id: int
    ) -> Optional[FormData]:
        """Process a raw form dict from the browser crawler."""
        html = raw_form.get("html", "")
        if not html:
            # Iframe-only form with no accessible content
            if raw_form.get("iframe_src"):
                return FormData(
                    company_id=company_id,
                    page_url=page_result.url,
                    form_type="contact",
                    iframe_src=raw_form["iframe_src"],
                    is_modal=raw_form.get("is_modal", False),
                    trigger_selector=raw_form.get("trigger", ""),
                    selectors=json.dumps({"iframe": raw_form.get("selector", "")}),
                )
            return None

        # Parse the form HTML
        parsed = self.parser.parse_form_html(html, page_result.url, page_result.html or "")
        if not parsed:
            return None

        return self._parsed_to_form_data(
            parsed, page_result, company_id,
            is_modal=raw_form.get("is_modal", False),
            trigger=raw_form.get("trigger", ""),
            iframe_src=raw_form.get("iframe_src", ""),
        )


    def _parsed_to_form_data(
        self,
        parsed: dict,
        page_result: PageResult,
        company_id: int,
        is_modal: bool = False,
        trigger: str = "",
        iframe_src: str = "",
    ) -> FormData:
        """Convert a parsed form dict into a FormData model."""
        # Extract JS event handlers from page HTML
        js_events = []
        if page_result.html:
            js_events = self._extract_js_events(parsed, page_result.html)

        # Build selectors JSON
        selectors = {
            "form": parsed.get("selector", ""),
            "submit_btn": self._find_submit_selector(parsed.get("html", "")),
            "inputs": self._find_input_selectors(parsed.get("html", "")),
        }

        return FormData(
            company_id=company_id,
            page_url=page_result.url,
            form_type=parsed.get("form_type", "contact"),
            html=parsed.get("html", "")[:10000],
            action=parsed.get("action", ""),
            method=parsed.get("method", "POST"),
            submit_type=parsed.get("submit_type", "form"),
            endpoint=parsed.get("endpoint", "") or parsed.get("action", ""),
            fields=parsed.get("fields", "[]"),
            hidden_fields=parsed.get("hidden_fields", "[]"),
            csrf_token=parsed.get("csrf_token", ""),
            captcha=parsed.get("captcha", "none"),
            selectors=json.dumps(selectors, ensure_ascii=False),
            xpath=parsed.get("xpath", ""),
            js_events=json.dumps(js_events, ensure_ascii=False),
            iframe_src=iframe_src,
            shadow_dom=False,
            is_modal=is_modal,
            trigger_selector=trigger,
        )


    def _extract_js_events(self, parsed: dict, page_html: str) -> list[dict]:
        """Extract JS event handlers related to this form."""
        events = []
        selector = parsed.get("selector", "")
        form_html = parsed.get("html", "")

        # Look for inline event handlers in form HTML
        inline_patterns = [
            (r'on(submit|click|change)\s*=\s*["\']([^"\']+)["\']', "inline"),
        ]
        for pattern, source in inline_patterns:
            for match in re.finditer(pattern, form_html, re.IGNORECASE):
                events.append({
                    "event": match.group(1),
                    "handler": match.group(2)[:200],
                    "source": source,
                })

        # Look for addEventListener patterns in page JS
        if selector:
            # Extract ID from selector
            id_match = re.search(r'#([\w-]+)', selector)
            if id_match:
                form_id = id_match.group(1)
                # Look for event listeners on this form
                listener_patterns = [
                    rf'getElementById\(["\']{ re.escape(form_id)}["\']\).*?addEventListener\(["\'](\w+)["\']',
                    rf'#{re.escape(form_id)}.*?\.(on|bind)\(["\'](\w+)["\']',
                ]
                for pat in listener_patterns:
                    for match in re.finditer(pat, page_html, re.DOTALL):
                        events.append({
                            "event": match.group(1),
                            "handler": "addEventListener",
                            "source": "script",
                        })

        # Look for AJAX/fetch calls near form references
        ajax_patterns = [
            (r'\$\.ajax\(\s*\{([^}]{10,300})\}', "jquery_ajax"),
            (r'fetch\(\s*["\']([^"\']+)["\']', "fetch"),
            (r'axios\.(post|get)\(\s*["\']([^"\']+)["\']', "axios"),
            (r'XMLHttpRequest.*?open\(\s*["\'](\w+)["\'],\s*["\']([^"\']+)["\']', "xhr"),
        ]
        for pattern, lib in ajax_patterns:
            for match in re.finditer(pattern, page_html, re.IGNORECASE | re.DOTALL):
                events.append({
                    "event": "submit",
                    "handler": match.group(0)[:200],
                    "source": lib,
                })
                break  # One per type is enough

        return events[:20]  # Cap at 20 events


    def _find_submit_selector(self, form_html: str) -> str:
        """Find CSS selector for the submit button."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(form_html, "lxml")

        # Look for submit button
        btn = soup.find("button", attrs={"type": "submit"})
        if not btn:
            btn = soup.find("input", attrs={"type": "submit"})
        if not btn:
            btn = soup.find("button")

        if btn:
            if btn.get("id"):
                return f"#{btn['id']}"
            classes = btn.get("class", [])
            if classes:
                return f"{btn.name}.{'.'.join(classes[:2])}"
            return btn.name
        return ""

    def _find_input_selectors(self, form_html: str) -> list[str]:
        """Find CSS selectors for form inputs."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(form_html, "lxml")
        selectors = []

        for inp in soup.find_all(["input", "textarea", "select"]):
            if inp.get("type") in ("hidden", "submit"):
                continue
            if inp.get("id"):
                selectors.append(f"#{inp['id']}")
            elif inp.get("name"):
                selectors.append(f'{inp.name}[name="{inp["name"]}"]')
            elif inp.get("class"):
                selectors.append(f"{inp.name}.{'.'.join(inp['class'][:2])}")

        return selectors

    def _is_duplicate(self, parsed_form: dict, existing_forms: list[FormData]) -> bool:
        """Check if a form is already in our list (by action + fields combo)."""
        action = parsed_form.get("action", "")
        fields = parsed_form.get("fields", "[]")

        for existing in existing_forms:
            if existing.action == action and existing.fields == fields:
                return True
        return False
