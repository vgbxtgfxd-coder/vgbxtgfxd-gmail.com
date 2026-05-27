"""
Модуль UI-автоматизации 1С через окно RDP (mstsc).

Сценарий (тестовый — дата и склад уже установлены в 1С):
1. Активировать RDP
2. Клик "Склад" в левом меню
3. Клик "Дополнительные отчёты"
4. Клик "Выполнить"
5. Клик "Сформировать"
6. Ждать формирования → Ctrl+S → ввести имя файла → Enter
"""
import time
import logging
from pathlib import Path
from datetime import datetime

import pyautogui
import pyperclip
import pygetwindow as gw

from config import (
    EXPORT_DIR,
    SCREENSHOTS_DIR,
    UI_ELEMENTS,
    UI_TIMEOUT_SHORT,
    UI_TIMEOUT_MEDIUM,
    UI_TIMEOUT_REPORT,
)

logger = logging.getLogger(__name__)

# Настройки pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def find_rdp_window():
    """Находит окно RDP-клиента"""
    all_windows = gw.getAllWindows()
    for win in all_windows:
        title = win.title.lower()
        if any(kw in title for kw in [
            "удалённый рабочий стол", "удаленный рабочий стол",
            "remote desktop", "mstsc",
        ]):
            return win
    for win in all_windows:
        if "РГК" in win.title or "ИПК" in win.title or "1С" in win.title or "1C" in win.title:
            return win
    return None


def activate_rdp_window() -> bool:
    """Активирует окно RDP"""
    rdp_win = find_rdp_window()

    if rdp_win:
        try:
            if rdp_win.isMinimized:
                rdp_win.restore()
            rdp_win.activate()
            time.sleep(1)
            center_x = rdp_win.left + rdp_win.width // 2
            center_y = rdp_win.top + rdp_win.height // 2
            pyautogui.click(center_x, center_y)
            time.sleep(0.5)
            logger.info(f"RDP-окно активировано: '{rdp_win.title}'")
            return True
        except Exception as e:
            logger.warning(f"Ошибка активации RDP: {e}")

    logger.warning("RDP-окно не найдено, пробую Alt+Tab")
    pyautogui.hotkey("alt", "tab")
    time.sleep(1.5)
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w // 2, screen_h // 2)
    time.sleep(0.5)
    return True


def generate_1c_report(warehouse_name: str, date_from: str, date_to: str) -> str | None:
    """
    Формирует отчёт в 1С и экспортирует в Excel.
    Тестовый режим: дата и склад уже установлены в 1С.
    Бот проходит путь: Склад → Доп.отчёты → Выполнить → Сформировать → Ctrl+S
    """
    try:
        logger.info(f"Начинаю формирование отчёта: {warehouse_name}, {date_from}-{date_to}")

        # 1. Активируем RDP
        if not activate_rdp_window():
            logger.error("Не удалось активировать RDP")
            return None
        time.sleep(UI_TIMEOUT_SHORT)

        # 2. Клик "Склад" в левом меню
        click_element("menu_sklad")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # 3. Клик "Дополнительные отчёты"
        click_element("btn_dop_reports")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # 4. Клик "Выполнить"
        click_element("btn_execute")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # 5. Клик "Сформировать"
        click_element("btn_generate")
        logger.info("Нажата кнопка 'Сформировать'")

        # 6. Ждём формирования отчёта
        logger.info(f"Ожидаю формирования отчёта ({UI_TIMEOUT_REPORT} сек)...")
        time.sleep(UI_TIMEOUT_REPORT)
        logger.info("Отчёт предположительно сформирован")

        # 7. Экспорт в Excel через Ctrl+S
        export_path = export_to_excel(warehouse_name, date_from)

        if export_path and Path(export_path).exists():
            logger.info(f"Отчёт сохранён: {export_path}")
            return export_path
        else:
            logger.error("Файл Excel не создан")
            take_screenshot("export_failed")
            return None

    except Exception as e:
        logger.exception(f"Ошибка автоматизации: {e}")
        take_screenshot("error")
        return None


def click_element(element_key: str):
    """Кликает по элементу из UI_ELEMENTS"""
    if element_key not in UI_ELEMENTS:
        logger.error(f"Элемент '{element_key}' не найден в UI_ELEMENTS. Запусти калибровку!")
        return
    coords = UI_ELEMENTS[element_key]
    pyautogui.click(coords["x"], coords["y"])
    logger.info(f"Клик: {element_key} ({coords['x']}, {coords['y']})")


def export_to_excel(warehouse_name: str, date_str: str) -> str | None:
    """
    Ctrl+S → ввод имени файла через tsclient → Enter
    """
    safe_name = warehouse_name.replace(" ", "_")
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"stock_{safe_name}_{timestamp}.xlsx"

    # Локальный путь (где файл окажется)
    local_path = str(EXPORT_DIR / filename)

    # Путь для 1С внутри RDP (через перенаправленный диск)
    rdp_save_path = (
        "\\\\tsclient\\C\\Users\\dhkgh\\"
        "vgbxtgfxd-gmail.com\\1c-stock-bot\\exports\\" + filename
    )

    try:
        # Ctrl+S
        pyautogui.hotkey("ctrl", "s")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Поле имени файла активно — очищаем и вводим путь
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.3)
        type_text_clipboard(rdp_save_path)
        time.sleep(1)

        # Enter = сохранить
        pyautogui.press("enter")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Подтверждение если спросит
        pyautogui.press("enter")
        time.sleep(UI_TIMEOUT_SHORT)

        # Проверяем файл
        if Path(local_path).exists():
            logger.info(f"Excel сохранён: {local_path}")
            return local_path

        # Проверяем .mxl
        mxl_path = local_path.replace(".xlsx", ".mxl")
        if Path(mxl_path).exists():
            logger.warning(f"Сохранено как .mxl: {mxl_path}")
            return mxl_path

        logger.error("Файл не появился. Проверь tsclient.")
        take_screenshot("export_no_file")
        return None

    except Exception as e:
        logger.exception(f"Ошибка экспорта: {e}")
        take_screenshot("export_exception")
        return None


def type_text_clipboard(text: str):
    """Ввод текста через буфер обмена (для кириллицы и путей)"""
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)


def take_screenshot(name: str) -> str:
    """Скриншот для отладки"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = str(SCREENSHOTS_DIR / f"{name}_{timestamp}.png")
    pyautogui.screenshot(path)
    logger.info(f"Скриншот: {path}")
    return path


if __name__ == "__main__":
    print("Поиск RDP-окна...")
    win = find_rdp_window()
    if win:
        print(f"Найдено: '{win.title}' [{win.width}x{win.height}]")
    else:
        print("RDP-окно не найдено.")
        print("\nВсе окна:")
        for w in gw.getAllWindows():
            if w.title.strip():
                print(f"  '{w.title}'")
