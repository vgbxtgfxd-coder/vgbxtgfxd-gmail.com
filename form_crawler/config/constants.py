"""Constants: categories, search templates, form triggers, pages to crawl."""

# Business categories for search
CATEGORIES = [
    "застройщики",
    "магазины",
    "мебель",
    "окна",
    "ремонт",
    "автосалоны",
    "стоматологии",
    "клиники",
    "агентства недвижимости",
    "производство",
    "услуги",
    "B2B компании",
]

# Search query templates - {category} will be substituted
SEARCH_TEMPLATES = [
    "{category} сайт",
    "{category} заказать звонок",
    "{category} оставить заявку",
    "{category} контакты",
    "{category} обратный звонок",
]

# Pages to crawl on each discovered site
PAGES_TO_CRAWL = [
    "/",
    "/contacts",
    "/contact",
    "/kontakty",
    "/callback",
    "/request",
    "/consultation",
    "/feedback",
    "/order",
    "/about",
    "/o-kompanii",
    "/uslugi",
    "/services",
    "/zayavka",
]

# Button/link text patterns that indicate callback/contact forms (Russian + English)
FORM_TRIGGERS = {
    "buttons": [
        "заказать звонок",
        "обратный звонок",
        "оставить заявку",
        "консультация",
        "получить предложение",
        "связаться",
        "отправить",
        "перезвоните мне",
        "заказать",
        "записаться",
        "получить консультацию",
        "бесплатная консультация",
        "рассчитать стоимость",
        "узнать цену",
        "оставить отзыв",
        "задать вопрос",
        "написать нам",
        "callback",
        "contact us",
        "request a call",
        "get a quote",
        "submit",
        "send",
    ],
    "form_types": {
        "callback": [
            "обратный звонок",
            "заказать звонок",
            "перезвоните",
            "callback",
            "request a call",
        ],
        "request": [
            "оставить заявку",
            "заявка",
            "отправить заявку",
            "request",
            "submit request",
        ],
        "consultation": [
            "консультация",
            "получить консультацию",
            "бесплатная консультация",
            "consultation",
        ],
        "contact": [
            "связаться",
            "написать нам",
            "контакты",
            "contact",
            "contact us",
        ],
        "quiz": [
            "квиз",
            "рассчитать",
            "калькулятор",
            "quiz",
            "calculate",
        ],
        "popup_callback": [
            "popup",
            "модальное окно",
            "modal",
            "dialog",
        ],
        "order": [
            "заказать",
            "оформить заказ",
            "купить",
            "order",
            "buy",
        ],
    },
}

# CSS selectors for finding interactive form elements
FORM_SELECTORS = {
    "forms": [
        "form",
        "[data-form]",
        "[class*='form']",
        "[class*='callback']",
        "[class*='feedback']",
        "[class*='contact']",
        "[class*='modal'] form",
        "[class*='popup'] form",
        "dialog form",
    ],
    "buttons": [
        "button",
        "a[href*='callback']",
        "a[href*='contact']",
        "[class*='callback']",
        "[class*='btn-call']",
        "[data-modal]",
        "[data-popup]",
        "[data-fancybox]",
        "[onclick*='modal']",
        "[onclick*='popup']",
        ".callback-btn",
        ".phone-btn",
        "#callback",
    ],
    "modals": [
        ".modal",
        ".popup",
        ".fancybox-container",
        "[class*='modal']",
        "[class*='popup']",
        "[class*='overlay']",
        "dialog",
        "[role='dialog']",
        "[aria-modal='true']",
    ],
    "iframes": [
        "iframe[src*='form']",
        "iframe[src*='callback']",
        "iframe[src*='quiz']",
        "iframe[src*='typeform']",
        "iframe[src*='google.com/forms']",
    ],
}

# Known CMS signatures
CMS_SIGNATURES = {
    "bitrix": [
        "bitrix",
        "/bitrix/",
        "BX.ready",
        "bx-session-id",
        "bitrix_sessid",
    ],
    "wordpress": [
        "wp-content",
        "wp-includes",
        "wp-json",
        "wordpress",
        "wpcf7",
    ],
    "tilda": [
        "tilda",
        "t-body",
        "t-records",
        "tildacdn",
        "t396",
    ],
    "joomla": [
        "joomla",
        "/components/",
        "/modules/",
        "task=",
    ],
    "drupal": [
        "drupal",
        "sites/default",
        "drupal.js",
    ],
    "modx": [
        "modx",
        "assets/components",
    ],
    "opencart": [
        "opencart",
        "route=",
        "catalog/view",
    ],
    "wix": [
        "wix.com",
        "wixstatic",
        "_wix",
    ],
    "squarespace": [
        "squarespace",
        "sqsp",
    ],
}

# Known JS libraries for forms
JS_LIBRARIES = {
    "jquery": ["jquery", "jQuery", "$.ajax"],
    "axios": ["axios"],
    "fetch_api": ["fetch("],
    "xmlhttprequest": ["XMLHttpRequest", "XHR"],
    "react": ["react", "React", "__NEXT_DATA__", "reactroot"],
    "vue": ["vue", "Vue", "__vue__"],
    "angular": ["angular", "ng-", "ng-app"],
    "recaptcha": ["recaptcha", "g-recaptcha", "grecaptcha"],
    "hcaptcha": ["hcaptcha", "h-captcha"],
    "bitrix_ajax": ["BX.ajax", "BX.proxy"],
    "wpcf7": ["wpcf7", "contact-form-7"],
}

# Anti-bot protection signatures
ANTIBOT_SIGNATURES = {
    "cloudflare": ["cf-browser-verification", "cloudflare", "__cf_bm", "cf_clearance"],
    "recaptcha": ["recaptcha", "g-recaptcha-response", "grecaptcha"],
    "hcaptcha": ["hcaptcha", "h-captcha-response"],
    "datadome": ["datadome"],
    "imperva": ["incapsula", "imperva", "_incap_"],
    "akamai": ["akamai", "_abck"],
    "kaspersky": ["kaspersky"],
    "qrator": ["qrator"],
    "ddos_guard": ["ddos-guard", "ddosguard"],
}

# User agents pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0",
]
