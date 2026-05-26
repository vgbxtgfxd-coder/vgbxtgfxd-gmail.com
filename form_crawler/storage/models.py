"""Data models for companies and forms."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Company:
    """Company entity."""

    id: Optional[int] = None
    name: str = ""
    site: str = ""
    category: str = ""
    city: str = ""
    cms: str = ""
    libraries: str = ""  # JSON list
    antibot: str = ""
    status: str = "pending"  # pending, crawled, error
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "site": self.site,
            "category": self.category,
            "city": self.city,
            "cms": self.cms,
            "libraries": self.libraries,
            "antibot": self.antibot,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class FormData:
    """Extracted form data."""

    id: Optional[int] = None
    company_id: int = 0
    page_url: str = ""
    form_type: str = ""  # callback, request, consultation, contact, quiz, popup_callback, order
    html: str = ""
    action: str = ""
    method: str = ""  # GET, POST
    submit_type: str = ""  # form, ajax, fetch, xhr
    endpoint: str = ""
    fields: str = ""  # JSON: [{name, type, required, placeholder, value}]
    hidden_fields: str = ""  # JSON
    csrf_token: str = ""
    captcha: str = ""  # none, recaptcha_v2, recaptcha_v3, hcaptcha
    selectors: str = ""  # JSON: {form, submit_btn, inputs}
    xpath: str = ""
    js_events: str = ""  # JSON: [event handlers]
    iframe_src: str = ""
    shadow_dom: bool = False
    is_modal: bool = False
    trigger_selector: str = ""  # selector of button that opens modal
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "page_url": self.page_url,
            "form_type": self.form_type,
            "html": self.html,
            "action": self.action,
            "method": self.method,
            "submit_type": self.submit_type,
            "endpoint": self.endpoint,
            "fields": self.fields,
            "hidden_fields": self.hidden_fields,
            "csrf_token": self.csrf_token,
            "captcha": self.captcha,
            "selectors": self.selectors,
            "xpath": self.xpath,
            "js_events": self.js_events,
            "iframe_src": self.iframe_src,
            "shadow_dom": self.shadow_dom,
            "is_modal": self.is_modal,
            "trigger_selector": self.trigger_selector,
            "created_at": self.created_at,
        }
