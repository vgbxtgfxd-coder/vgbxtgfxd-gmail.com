"""Tests for the HTML form parser."""

import json
import pytest

from form_crawler.parser.html_parser import FormParser


@pytest.fixture
def parser():
    return FormParser()


SAMPLE_CALLBACK_FORM = """
<html><body>
<div class="modal callback-modal">
  <h3>Заказать обратный звонок</h3>
  <form id="callback-form" action="/ajax/callback.php" method="POST">
    <input type="hidden" name="csrf_token" value="tok123" />
    <input type="text" name="name" placeholder="Ваше имя" required />
    <input type="tel" name="phone" placeholder="+7 (___) ___-__-__" required />
    <button type="submit">Перезвоните мне</button>
  </form>
</div>
</body></html>
"""

SAMPLE_CONTACT_FORM = """
<html><body>
<section class="contacts">
  <form action="/send-feedback" method="POST" class="feedback-form">
    <input type="text" name="name" id="name" placeholder="Имя" />
    <input type="email" name="email" id="email" placeholder="Email" required />
    <input type="tel" name="phone" id="phone" placeholder="Телефон" />
    <textarea name="message" placeholder="Сообщение"></textarea>
    <div class="g-recaptcha" data-sitekey="xxx"></div>
    <button type="submit">Отправить</button>
  </form>
</section>
</body></html>
"""

SAMPLE_DIV_FORM = """
<html><body>
<div class="callback-widget">
  <p>Оставьте заявку и мы перезвоним</p>
  <input type="text" name="name" placeholder="Имя" />
  <input type="tel" name="phone" placeholder="Телефон" required />
  <button onclick="sendCallback()">Заказать звонок</button>
</div>
</body></html>
"""

SAMPLE_SEARCH_FORM = """
<html><body>
<form action="/search" method="GET">
  <input type="search" name="q" placeholder="Поиск..." />
  <button type="submit">Найти</button>
</form>
</body></html>
"""

SAMPLE_LOGIN_FORM = """
<html><body>
<form action="/auth/login" method="POST">
  <input type="text" name="login" placeholder="Логин" />
  <input type="password" name="password" placeholder="Пароль" />
  <button type="submit">Войти</button>
</form>
</body></html>
"""


class TestFormParser:
    def test_detects_callback_form(self, parser):
        results = parser.parse_page(SAMPLE_CALLBACK_FORM, "https://example.com/")
        assert len(results) == 1
        form = results[0]
        assert form["form_type"] == "callback"
        assert form["action"] == "https://example.com/ajax/callback.php"
        assert form["method"] == "POST"

    def test_extracts_fields(self, parser):
        results = parser.parse_page(SAMPLE_CALLBACK_FORM, "https://example.com/")
        form = results[0]
        fields = json.loads(form["fields"])
        assert len(fields) == 2
        assert fields[0]["purpose"] == "name"
        assert fields[1]["purpose"] == "phone"

    def test_extracts_hidden_fields_and_csrf(self, parser):
        results = parser.parse_page(SAMPLE_CALLBACK_FORM, "https://example.com/")
        form = results[0]
        hidden = json.loads(form["hidden_fields"])
        assert len(hidden) == 1
        assert hidden[0]["name"] == "csrf_token"
        assert form["csrf_token"] == "tok123"

    def test_detects_contact_form(self, parser):
        results = parser.parse_page(SAMPLE_CONTACT_FORM, "https://example.com/contacts")
        assert len(results) == 1
        form = results[0]
        assert form["form_type"] == "contact"

    def test_detects_recaptcha(self, parser):
        results = parser.parse_page(SAMPLE_CONTACT_FORM, "https://example.com/contacts")
        form = results[0]
        assert form["captcha"] == "recaptcha_v2"

    def test_detects_div_based_form(self, parser):
        results = parser.parse_page(SAMPLE_DIV_FORM, "https://example.com/")
        assert len(results) >= 1
        form = results[0]
        assert form["form_type"] == "callback"

    def test_filters_search_form(self, parser):
        results = parser.parse_page(SAMPLE_SEARCH_FORM, "https://example.com/")
        assert len(results) == 0

    def test_filters_login_form(self, parser):
        results = parser.parse_page(SAMPLE_LOGIN_FORM, "https://example.com/")
        assert len(results) == 0

    def test_builds_css_selector(self, parser):
        results = parser.parse_page(SAMPLE_CALLBACK_FORM, "https://example.com/")
        form = results[0]
        assert "#callback-form" in form["selector"]

    def test_builds_xpath(self, parser):
        results = parser.parse_page(SAMPLE_CALLBACK_FORM, "https://example.com/")
        form = results[0]
        assert "callback-form" in form["xpath"]
