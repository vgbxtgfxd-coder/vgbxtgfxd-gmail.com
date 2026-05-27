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

# Координаты UI-элементов 1С (внутри RDP)
# Калибруются через: python calibrate.py
UI_ELEMENTS = {
    "menu_sklad": {"x": 60, "y": 114},          # "Склад" в левом меню
    "btn_dop_reports": {"x": 395, "y": 145},     # "Дополнительные отчёты"
    "btn_execute": {"x": 697, "y": 523},         # "Выполнить" в окне доп.отчётов
    "btn_generate": {"x": 186, "y": 130},        # "Сформировать" в форме отчёта
}
