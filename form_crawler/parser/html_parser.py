"""HTML parser for detecting and classifying forms on pages."""

import re
import json
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from lxml import html as lxml_html
from selectolax.parser import HTMLParser as SelectolaxParser

from ..config.constants import FORM_TRIGGERS, CMS_SIGNATURES

logger = logging.getLogger(__name__)


class FormParser:
    """Parses raw HTML to detect, classify, and extract form structures."""

    def __init__(self):
        self._form_type_keywords = FORM_TRIGGERS["form_types"]

    def parse_page(self, page_html: str, page_url: str) -> list[dict]:
        """Parse a full page HTML and return all detected forms with metadata.

        Returns list of dicts:
            {
                html: str,
                action: str,
                method: str,
                form_type: str,
                fields: list[dict],
                hidden_fields: list[dict],
                csrf_token: str,
                captcha: str,
                selector: str,
                xpath: str,
                submit_type: str,
                endpoint: str,
            }
        """
        soup = BeautifulSoup(page_html, "lxml")
        results = []

        # Find all <form> elements
        forms = soup.find_all("form")
        for form in forms:
            parsed = self._parse_form_element(form, page_url, page_html)
            if parsed and self._is_relevant_form(parsed):
                results.append(parsed)

        # Also look for div-based "forms" (no <form> tag but has inputs + button)
        div_forms = self._find_div_forms(soup, page_url, page_html)
        results.extend(div_forms)

        return results

    def parse_form_html(self, form_html: str, page_url: str, page_html: str = "") -> Optional[dict]:
        """Parse a single form HTML snippet."""
        soup = BeautifulSoup(form_html, "lxml")
        form = soup.find("form")
        if form:
            return self._parse_form_element(form, page_url, page_html)

        # Maybe it's a div-based form
        container = soup.find(["div", "section", "dialog"])
        if container:
            inputs = container.find_all(["input", "textarea", "select"])
            if inputs:
                return self._parse_container_as_form(container, page_url, page_html)
        return None

    def _parse_form_element(self, form: Tag, page_url: str, page_html: str) -> dict:
        """Extract all metadata from a <form> element."""
        # Basic attributes
        action = form.get("action", "")
        method = (form.get("method", "POST")).upper()
        form_id = form.get("id", "")
        form_class = " ".join(form.get("class", []))
        form_name = form.get("name", "")

        # Resolve action URL
        if action and not action.startswith(("http://", "https://", "javascript:")):
            action = urljoin(page_url, action)

        # Extract fields
        fields = self._extract_fields(form)
        hidden_fields = [f for f in fields if f["type"] == "hidden"]
        visible_fields = [f for f in fields if f["type"] != "hidden"]

        # CSRF token detection
        csrf_token = self._detect_csrf(hidden_fields)

        # Captcha detection
        captcha = self._detect_captcha(form, page_html)

        # Form type classification
        form_type = self._classify_form(form, visible_fields)

        # CSS selector
        selector = self._build_css_selector(form)

        # XPath
        xpath = self._build_xpath(form)

        # Detect submit type (form submit vs AJAX)
        submit_type, endpoint = self._detect_submit_type(form, page_html, form_id, form_class)

        # If submit_type is ajax/fetch, endpoint might differ from action
        if not endpoint and action:
            endpoint = action

        return {
            "html": str(form)[:10000],
            "action": action,
            "method": method,
            "form_type": form_type,
            "fields": json.dumps(visible_fields, ensure_ascii=False),
            "hidden_fields": json.dumps(hidden_fields, ensure_ascii=False),
            "csrf_token": csrf_token,
            "captcha": captcha,
            "selector": selector,
            "xpath": xpath,
            "submit_type": submit_type,
            "endpoint": endpoint,
        }

    def _parse_container_as_form(self, container: Tag, page_url: str, page_html: str) -> dict:
        """Parse a div/section that acts as a form (no <form> tag)."""
        fields = self._extract_fields(container)
        hidden_fields = [f for f in fields if f["type"] == "hidden"]
        visible_fields = [f for f in fields if f["type"] != "hidden"]

        form_type = self._classify_form(container, visible_fields)
        selector = self._build_css_selector(container)
        xpath = self._build_xpath(container)

        # For div forms, submit is almost always AJAX
        submit_type = "ajax"
        endpoint = ""

        # Try to find endpoint from onclick or data attributes on button
        submit_btn = container.find(["button", "input"], attrs={"type": "submit"})
        if not submit_btn:
            submit_btn = container.find("button")
        if submit_btn:
            onclick = submit_btn.get("onclick", "")
            endpoint = self._extract_url_from_js(onclick)

        return {
            "html": str(container)[:10000],
            "action": "",
            "method": "POST",
            "form_type": form_type,
            "fields": json.dumps(visible_fields, ensure_ascii=False),
            "hidden_fields": json.dumps(hidden_fields, ensure_ascii=False),
            "csrf_token": self._detect_csrf(hidden_fields),
            "captcha": self._detect_captcha(container, page_html),
            "selector": selector,
            "xpath": xpath,
            "submit_type": submit_type,
            "endpoint": endpoint,
        }

    def _extract_fields(self, container: Tag) -> list[dict]:
        """Extract all input/textarea/select fields from container."""
        fields = []

        for inp in container.find_all(["input", "textarea", "select"]):
            field = {
                "tag": inp.name,
                "name": inp.get("name", ""),
                "type": inp.get("type", "text") if inp.name == "input" else inp.name,
                "id": inp.get("id", ""),
                "placeholder": inp.get("placeholder", ""),
                "value": inp.get("value", ""),
                "required": inp.has_attr("required"),
                "class": " ".join(inp.get("class", [])),
                "data_attrs": {k: v for k, v in inp.attrs.items() if k.startswith("data-")},
            }

            # Try to find associated label
            field_id = inp.get("id")
            if field_id:
                label = container.find("label", attrs={"for": field_id})
                if label:
                    field["label"] = label.get_text(strip=True)

            # Classify field purpose
            field["purpose"] = self._classify_field_purpose(field)

            fields.append(field)

        return fields

    def _classify_field_purpose(self, field: dict) -> str:
        """Classify what a field is for: name, phone, email, comment, etc."""
        name = (field.get("name", "") + " " + field.get("placeholder", "") + " " +
                field.get("id", "") + " " + field.get("label", "")).lower()

        if any(x in name for x in ["phone", "телефон", "тел", "tel", "mob"]):
            return "phone"
        if any(x in name for x in ["email", "e-mail", "почта", "mail"]):
            return "email"
        if any(x in name for x in ["name", "имя", "фио", "fio", "firstname", "lastname"]):
            return "name"
        if any(x in name for x in ["comment", "комментарий", "message", "сообщение", "текст", "text"]):
            return "comment"
        if any(x in name for x in ["city", "город", "gorod"]):
            return "city"
        if any(x in name for x in ["company", "компания", "организация"]):
            return "company"
        if field["type"] == "hidden":
            return "hidden"
        return "other"

    def _classify_form(self, container: Tag, visible_fields: list[dict]) -> str:
        """Classify form type based on content, button text, and field composition."""
        # Collect all text in the form area
        text = container.get_text(" ", strip=True).lower()

        # Also check parent for context
        parent = container.parent
        parent_text = ""
        if parent:
            # Get text from headings near the form
            headings = parent.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"], limit=3)
            parent_text = " ".join(h.get_text(strip=True).lower() for h in headings)

        combined_text = text + " " + parent_text

        # Match against known form type keywords
        for form_type, keywords in self._form_type_keywords.items():
            for kw in keywords:
                if kw.lower() in combined_text:
                    return form_type

        # Fallback heuristics based on field composition
        purposes = {f["purpose"] for f in visible_fields}
        if "phone" in purposes and len(visible_fields) <= 3:
            return "callback"
        if "email" in purposes and "comment" in purposes:
            return "contact"
        if len(visible_fields) >= 5:
            return "quiz"

        return "contact"

    def _detect_csrf(self, hidden_fields: list[dict]) -> str:
        """Find CSRF token in hidden fields."""
        csrf_patterns = [
            "csrf", "token", "_token", "sessid", "nonce",
            "bitrix_sessid", "wp_nonce", "csrfmiddlewaretoken",
        ]
        for field in hidden_fields:
            name = field.get("name", "").lower()
            for pattern in csrf_patterns:
                if pattern in name:
                    return field.get("value", "")
        return ""

    def _detect_captcha(self, container: Tag, page_html: str) -> str:
        """Detect captcha type."""
        container_html = str(container).lower()
        page_lower = page_html.lower()

        if "g-recaptcha" in container_html or "recaptcha" in container_html:
            if "recaptcha/api.js?render=" in page_lower:
                return "recaptcha_v3"
            return "recaptcha_v2"
        if "hcaptcha" in container_html or "h-captcha" in container_html:
            return "hcaptcha"
        if "recaptcha" in page_lower:
            if "recaptcha/api.js?render=" in page_lower:
                return "recaptcha_v3"
            return "recaptcha_v2"
        if "hcaptcha" in page_lower:
            return "hcaptcha"
        return "none"

    def _detect_submit_type(self, form: Tag, page_html: str, form_id: str, form_class: str) -> tuple[str, str]:
        """Detect how the form is submitted: standard form POST, AJAX, fetch, XHR."""
        # Check for onsubmit handler
        onsubmit = form.get("onsubmit", "")
        if onsubmit:
            if "return false" in onsubmit or "preventDefault" in onsubmit:
                endpoint = self._extract_url_from_js(onsubmit)
                return "ajax", endpoint

        # Check for common AJAX patterns in page JS
        # Look for form ID/class being referenced in JS with AJAX
        if form_id or form_class:
            identifier = form_id or form_class.split()[0] if form_class else ""
            if identifier:
                # Search for AJAX handlers targeting this form
                patterns = [
                    rf"['\"]#{re.escape(identifier)}['\"].*?\.submit",
                    rf"['\"]#{re.escape(identifier)}['\"].*?ajax",
                    rf"document\.getElementById\(['\"]{ re.escape(identifier)}['\"]\).*?fetch",
                    rf"\.{re.escape(identifier)}.*?ajax",
                ]
                for pattern in patterns:
                    match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
                    if match:
                        # Try to extract endpoint
                        context = page_html[max(0, match.start() - 50):match.end() + 200]
                        endpoint = self._extract_url_from_js(context)
                        if "fetch" in pattern:
                            return "fetch", endpoint
                        return "ajax", endpoint

        # Check for common form libraries
        page_lower = page_html.lower()
        if "wpcf7" in page_lower and form_class and "wpcf7" in form_class:
            return "ajax", ""
        if "bx.ajax" in page_lower or "BX.ajax" in page_html:
            return "ajax", ""

        # Check form action - if it's # or empty, likely AJAX
        action = form.get("action", "")
        if action in ("", "#", "javascript:void(0)", "javascript:;"):
            return "ajax", ""

        return "form", ""

    def _extract_url_from_js(self, js_code: str) -> str:
        """Try to extract a URL/endpoint from JavaScript code."""
        # Look for URL patterns in JS
        url_patterns = [
            r"""(?:url|action|href|endpoint|api)\s*[:=]\s*['"](\/[^'"]+)['"]""",
            r"""fetch\(\s*['"](\/[^'"]+)['"]""",
            r"""\.ajax\(\s*\{[^}]*url\s*:\s*['"](\/[^'"]+)['"]""",
            r"""XMLHttpRequest[^;]*open\([^,]*,\s*['"](\/[^'"]+)['"]""",
            r"""['"](\/api\/[^'"]+)['"]""",
            r"""['"](\/(?:ajax|callback|submit|send|form)[^'"]*?)['"]""",
        ]

        for pattern in url_patterns:
            match = re.search(pattern, js_code, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _find_div_forms(self, soup: BeautifulSoup, page_url: str, page_html: str) -> list[dict]:
        """Find div-based forms (inputs + button but no <form> tag)."""
        results = []

        # Look for containers with inputs that aren't inside a <form>
        for container in soup.find_all(["div", "section"], class_=re.compile(
            r"(form|callback|feedback|contact|modal|popup)", re.I
        )):
            # Skip if it's inside an existing form
            if container.find_parent("form"):
                continue
            # Skip if it already contains a <form>
            if container.find("form"):
                continue

            inputs = container.find_all(["input", "textarea", "select"])
            has_button = container.find(["button"]) or container.find("input", type="submit")

            if len(inputs) >= 1 and has_button:
                parsed = self._parse_container_as_form(container, page_url, page_html)
                if parsed and self._is_relevant_form(parsed):
                    results.append(parsed)

        return results

    def _is_relevant_form(self, parsed_form: dict) -> bool:
        """Filter out irrelevant forms (search bars, login forms, etc.)."""
        fields = json.loads(parsed_form.get("fields", "[]"))

        # Must have at least one relevant field
        purposes = {f.get("purpose") for f in fields}
        relevant_purposes = {"phone", "email", "name", "comment"}

        if not purposes.intersection(relevant_purposes):
            # Check if it's a search form
            if len(fields) == 1 and fields[0].get("type") == "search":
                return False
            # Single text input with no phone/email - probably search
            if len(fields) == 1:
                name = fields[0].get("name", "").lower()
                if any(x in name for x in ["search", "query", "q", "поиск"]):
                    return False

        # Skip login forms
        if any(f.get("type") == "password" for f in fields):
            return False

        return True

    @staticmethod
    def _build_css_selector(tag: Tag) -> str:
        """Build a CSS selector for a BeautifulSoup tag."""
        parts = []
        current = tag
        while current and current.name and current.name != "[document]":
            selector = current.name
            if current.get("id"):
                selector += f"#{current['id']}"
                parts.insert(0, selector)
                break
            else:
                classes = current.get("class", [])
                if classes:
                    selector += "." + ".".join(classes[:2])  # limit to 2 classes
                # Add nth-of-type if needed
                siblings = current.find_previous_siblings(current.name)
                if siblings:
                    selector += f":nth-of-type({len(siblings) + 1})"
            parts.insert(0, selector)
            current = current.parent
        return " > ".join(parts[-5:])  # Keep last 5 levels max

    @staticmethod
    def _build_xpath(tag: Tag) -> str:
        """Build an XPath expression for a BeautifulSoup tag."""
        parts = []
        current = tag
        while current and current.name and current.name != "[document]":
            part = current.name
            if current.get("id"):
                parts.insert(0, f'//*[@id="{current["id"]}"]')
                break
            else:
                siblings = current.find_previous_siblings(current.name)
                idx = len(siblings) + 1
                part = f"{current.name}[{idx}]"
            parts.insert(0, part)
            current = current.parent

        if parts and parts[0].startswith("//*"):
            return parts[0] + "/" + "/".join(parts[1:]) if len(parts) > 1 else parts[0]
        return "//" + "/".join(parts[-4:])  # Keep last 4 levels
