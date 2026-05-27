"""
Конфигурация бота складских остатков 1С
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = [int(uid) for uid in os.getenv("ALLOWED_USERS", "").split(",") if uid.strip()]

# Пути
BASE_DIR = Path(__file__).parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# Склады (как отображаются в выпадающем списке 1С)
WAREHOUSES = {
    "томилино": "склад Томилино",
    "дедовск": "Склад Дедовск",
    "богородское": "Склад БОГОРОДСКОЕ",
    "песчаные": "Склад Песчаные ковали",
    "ковали": "Склад Песчаные ковали",
    "синтез": "Склад СИНТЕЗ",
}

# Таймауты UI-автоматизации (секунды)
UI_TIMEOUT_SHORT = 2
UI_TIMEOUT_MEDIUM = 5
UI_TIMEOUT_LONG = 15
UI_TIMEOUT_REPORT = 30  # формирование отчёта может быть долгим

# 1С - координаты элементов интерфейса
# ВАЖНО: эти координаты нужно будет откалибровать под конкретный экран RDP
# Используй команду /calibrate в боте для настройки
UI_ELEMENTS = {
    "date_start": {"x": 192, "y": 93},       # поле даты начала
    "date_end": {"x": 307, "y": 93},         # поле даты конца
    "warehouse_checkbox": {"x": 867, "y": 93},  # чекбокс "Склад"
    "warehouse_field": {"x": 1050, "y": 93},    # поле выбора склада
    "btn_generate": {"x": 186, "y": 130},       # кнопка "Сформировать"
    "nomenclature_field": {"x": 630, "y": 93},  # поле "Номенклатура труб"
}

# Координаты для экспорта
UI_EXPORT = {
    "menu_file": {"x": 0, "y": 0},           # будет калиброваться
    "save_as_excel": {"x": 0, "y": 0},       # будет калиброваться
}
