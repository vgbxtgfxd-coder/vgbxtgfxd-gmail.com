"""
Модуль UI-автоматизации 1С
Управляет интерфейсом 1С через pyautogui для формирования отчётов по остаткам.

Предполагает что:
- RDP-сессия открыта и активна
- 1С уже запущена с открытым отчётом "ОСВ по номенклатуре и заказам"
"""
import time
import logging
from pathlib import Path
from datetime import datetime

import pyautogui
import pyperclip

from config import (
    EXPORT_DIR,
    SCREENSHOTS_DIR,
    WAREHOUSES,
    UI_ELEMENTS,
    UI_TIMEOUT_SHORT,
    UI_TIMEOUT_MEDIUM,
    UI_TIMEOUT_LONG,
    UI_TIMEOUT_REPORT,
)

logger = logging.getLogger(__name__)

# Настройки pyautogui
pyautogui.FAILSAFE = True  # мышь в угол = экстренная остановка
pyautogui.PAUSE = 0.3       # пауза между действиями


def generate_1c_report(warehouse_name: str, date_from: str, date_to: str) -> str | None:
    """
    Формирует отчёт в 1С и экспортирует в Excel.

    Args:
        warehouse_name: Полное название склада как в 1С
        date_from: Дата начала (ДД.ММ.ГГГГ)
        date_to: Дата конца (ДД.ММ.ГГГГ)

    Returns:
        Путь к сохранённому Excel-файлу или None при ошибке
    """
    try:
        logger.info(f"Начинаю формирование отчёта: {warehouse_name}, {date_from}-{date_to}")

        # Активируем окно 1С
        if not activate_1c_window():
            logger.error("Не удалось активировать окно 1С")
            return None

        time.sleep(UI_TIMEOUT_SHORT)

        # Устанавливаем дату начала
        set_date_field("date_start", date_from)
        time.sleep(0.5)

        # Устанавливаем дату конца
        set_date_field("date_end", date_to)
        time.sleep(0.5)

        # Выбираем склад
        select_warehouse(warehouse_name)
        time.sleep(UI_TIMEOUT_SHORT)

        # Нажимаем "Сформировать"
        click_generate()
        time.sleep(UI_TIMEOUT_REPORT)  # ждём формирования отчёта

        # Ждём пока отчёт сформируется (проверяем по наличию данных)
        if not wait_for_report():
            logger.error("Отчёт не сформировался за отведённое время")
            take_screenshot("report_timeout")
            return None

        # Экспортируем в Excel
        export_path = export_to_excel(warehouse_name, date_from)

        if export_path and Path(export_path).exists():
            logger.info(f"Отчёт сохранён: {export_path}")
            return export_path
        else:
            logger.error("Файл Excel не создан")
            take_screenshot("export_failed")
            return None

    except Exception as e:
        logger.exception(f"Ошибка автоматизации 1С: {e}")
        take_screenshot("error")
        return None


def activate_1c_window() -> bool:
    """Активирует окно 1С (ищет по заголовку)"""
    try:
        import pygetwindow as gw

        windows = gw.getWindowsWithTitle("1С:Предприятие")
        if not windows:
            windows = gw.getWindowsWithTitle("1C:Предприятие")
        if not windows:
            # Попробуем найти по части заголовка
            all_wins = gw.getAllWindows()
            windows = [w for w in all_wins if "1С" in w.title or "1C" in w.title]

        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(1)
            return True
        else:
            logger.warning("Окно 1С не найдено. Убедись что 1С запущена.")
            return False

    except ImportError:
        # Если pygetwindow недоступен — пробуем через Alt+Tab или координаты
        logger.warning("pygetwindow не установлен, используем клик по панели задач")
        # Кликаем по иконке 1С в панели задач (нужно будет откалибровать)
        pyautogui.hotkey("alt", "tab")
        time.sleep(1)
        return True


def set_date_field(field_key: str, date_str: str):
    """Устанавливает дату в поле 1С"""
    coords = UI_ELEMENTS[field_key]
    x, y = coords["x"], coords["y"]

    # Тройной клик чтобы выделить всё содержимое поля
    pyautogui.click(x, y, clicks=3)
    time.sleep(0.3)

    # Очищаем и вводим новую дату
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)

    # Вводим дату
    pyautogui.typewrite(date_str.replace(".", ""), interval=0.05)
    time.sleep(0.3)
    pyautogui.press("enter")


def select_warehouse(warehouse_name: str):
    """Выбирает склад из выпадающего списка"""
    coords = UI_ELEMENTS["warehouse_field"]
    x, y = coords["x"], coords["y"]

    # Кликаем по полю склада
    pyautogui.click(x, y, clicks=3)
    time.sleep(0.5)

    # Очищаем поле
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.2)

    # Вводим название склада через буфер обмена (для кириллицы)
    type_text_clipboard(warehouse_name)
    time.sleep(UI_TIMEOUT_MEDIUM)

    # Нажимаем Enter для подтверждения выбора
    pyautogui.press("enter")
    time.sleep(0.5)


def click_generate():
    """Нажимает кнопку 'Сформировать'"""
    coords = UI_ELEMENTS["btn_generate"]
    pyautogui.click(coords["x"], coords["y"])
    logger.info("Нажата кнопка 'Сформировать'")


def wait_for_report(timeout: int = 60, check_interval: float = 2.0) -> bool:
    """
    Ждёт формирования отчёта.
    Проверяет что курсор вернулся в обычное состояние (не песочные часы).
    """
    start = time.time()
    while time.time() - start < timeout:
        # Проверяем что 1С не показывает "занят" — курсор не песочные часы
        # Простая проверка: пытаемся кликнуть и проверяем реакцию
        time.sleep(check_interval)

        # Делаем скриншот маленькой области с данными
        # Если появились числа — отчёт готов
        screenshot = pyautogui.screenshot(
            region=(400, 200, 200, 50)  # область где должны быть данные
        )
        # Грубая проверка: если пиксели в этой области изменились (не пустой фон)
        pixels = list(screenshot.getdata())
        non_white = sum(1 for p in pixels if p[0] < 240 or p[1] < 240 or p[2] < 240)
        if non_white > 100:  # есть контент
            logger.info("Отчёт сформирован")
            return True

    return False


def export_to_excel(warehouse_name: str, date_str: str) -> str | None:
    """
    Экспортирует текущий отчёт в Excel через Ctrl+S.
    
    1С при нажатии Ctrl+S в отчёте открывает диалог "Сохранить как".
    Вводим путь к файлу и подтверждаем.
    """
    # Формируем имя файла
    safe_name = warehouse_name.replace(" ", "_")
    safe_date = date_str.replace(".", "-")
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"stock_{safe_name}_{safe_date}_{timestamp}.xlsx"
    export_path = str(EXPORT_DIR / filename)

    try:
        # Ctrl+S — открывает диалог "Сохранить как" в 1С
        pyautogui.hotkey("ctrl", "s")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Диалог "Сохранить как" открылся
        # Очищаем поле имени файла и вводим наш путь
        # В стандартном диалоге Windows поле имени файла уже активно
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.3)

        # Вводим полный путь к файлу через буфер обмена
        type_text_clipboard(export_path)
        time.sleep(1)

        # Проверяем тип файла — нужен xlsx
        # Tab переключает на выпадающий список типа файла
        pyautogui.press("tab")
        time.sleep(0.3)

        # Если нужно выбрать формат — вводим xlsx
        # В 1С обычно по умолчанию предлагает xlsx или mxl
        # Возвращаемся к кнопке "Сохранить"
        pyautogui.hotkey("alt", "s")  # Alt+S = "Сохранить" в русской локали
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Если файл не сохранился через Alt+S — пробуем Enter
        if not Path(export_path).exists():
            pyautogui.press("enter")
            time.sleep(UI_TIMEOUT_MEDIUM)

        # Если 1С спрашивает подтверждение перезаписи — подтверждаем
        if not Path(export_path).exists():
            pyautogui.press("enter")
            time.sleep(UI_TIMEOUT_SHORT)

        # Финальная проверка
        if Path(export_path).exists():
            logger.info(f"Excel сохранён: {export_path}")
            return export_path

        # Если стандартный путь не сработал — пробуем альтернативу
        # Некоторые версии 1С сохраняют в формат .mxl, а не .xlsx
        # Проверяем .mxl вариант
        mxl_path = export_path.replace(".xlsx", ".mxl")
        if Path(mxl_path).exists():
            logger.warning(f"1С сохранила в .mxl вместо .xlsx: {mxl_path}")
            # TODO: конвертация mxl → xlsx при необходимости
            return mxl_path

        logger.error("Файл не создан после Ctrl+S")
        take_screenshot("export_ctrl_s_failed")
        return None

    except Exception as e:
        logger.exception(f"Ошибка экспорта: {e}")
        take_screenshot("export_exception")
        return None


def type_text_clipboard(text: str):
    """
    Вводит текст через буфер обмена (для кириллицы).
    pyautogui.typewrite() не работает с кириллицей.
    """
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)


def take_screenshot(name: str) -> str:
    """Делает скриншот для отладки"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = str(SCREENSHOTS_DIR / f"{name}_{timestamp}.png")
    pyautogui.screenshot(path)
    logger.info(f"Скриншот: {path}")
    return path


def calibrate_ui() -> dict:
    """
    Утилита калибровки: определяет текущие координаты мыши.
    Запускается вручную для настройки UI_ELEMENTS.
    """
    print("=== Калибровка UI-элементов 1С ===")
    print("Наведи мышь на нужный элемент и нажми Enter.")
    print("Для выхода напиши 'q'\n")

    elements = {}
    targets = [
        ("date_start", "Поле даты начала"),
        ("date_end", "Поле даты конца"),
        ("warehouse_checkbox", "Чекбокс 'Склад'"),
        ("warehouse_field", "Поле выбора склада"),
        ("btn_generate", "Кнопка 'Сформировать'"),
        ("nomenclature_field", "Поле 'Номенклатура труб'"),
    ]

    for key, label in targets:
        inp = input(f"  Наведи на [{label}] и нажми Enter (q=выход): ")
        if inp.lower() == "q":
            break
        pos = pyautogui.position()
        elements[key] = {"x": pos.x, "y": pos.y}
        print(f"    → {key}: x={pos.x}, y={pos.y}")

    print("\n=== Результат ===")
    print("UI_ELEMENTS = {")
    for key, coords in elements.items():
        print(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},')
    print("}")

    return elements


if __name__ == "__main__":
    # Запуск калибровки
    calibrate_ui()
