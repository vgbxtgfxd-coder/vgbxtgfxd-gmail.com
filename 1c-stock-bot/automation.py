"""
Модуль UI-автоматизации 1С через окно RDP (mstsc).

Бот работает на локальном ПК, 1С запущена внутри RDP-сессии.
Бот находит окно RDP-клиента, активирует его и кликает внутри.
Координаты калибровки — абсолютные (экранные) при полноэкранном RDP.
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


def find_rdp_window():
    """Находит окно RDP-клиента (mstsc)"""
    # Ищем по типичным заголовкам RDP-окна
    all_windows = gw.getAllWindows()
    for win in all_windows:
        title = win.title.lower()
        # RDP-окна обычно содержат имя сервера или "удалённый рабочий стол"
        if any(keyword in title for keyword in [
            "удалённый рабочий стол",
            "удаленный рабочий стол",
            "remote desktop",
            "mstsc",
            # Также может быть просто имя сервера
        ]):
            return win

    # Если не нашли по стандартным заголовкам — ищем окно mstsc по процессу
    # Fallback: ищем любое окно с характерным размером (полноэкранное)
    for win in all_windows:
        if "РГК" in win.title or "ИПК" in win.title or "1С" in win.title:
            return win

    return None


def activate_rdp_window() -> bool:
    """Активирует окно RDP и кликает внутри для фокуса"""
    rdp_win = find_rdp_window()

    if rdp_win:
        try:
            if rdp_win.isMinimized:
                rdp_win.restore()
            rdp_win.activate()
            time.sleep(1)
            # Клик в центр окна чтобы RDP получил фокус
            center_x = rdp_win.left + rdp_win.width // 2
            center_y = rdp_win.top + rdp_win.height // 2
            pyautogui.click(center_x, center_y)
            time.sleep(0.5)
            logger.info(f"RDP-окно активировано: '{rdp_win.title}'")
            return True
        except Exception as e:
            logger.warning(f"Ошибка активации RDP-окна: {e}")

    # Fallback: если RDP в полноэкранном режиме — он уже активен
    # Просто кликаем в центр экрана
    logger.warning("RDP-окно не найдено по заголовку, пробую активировать через Alt+Tab")
    pyautogui.hotkey("alt", "tab")
    time.sleep(1.5)
    # Клик в центр экрана
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w // 2, screen_h // 2)
    time.sleep(0.5)
    return True


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

        # Активируем окно RDP
        if not activate_rdp_window():
            logger.error("Не удалось активировать окно RDP")
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

        # Ждём пока отчёт сформируется
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

    # Вводим дату цифрами (без точек — 1С сама расставит)
    pyautogui.typewrite(date_str.replace(".", ""), interval=0.05)
    time.sleep(0.3)
    pyautogui.press("enter")
    logger.info(f"Дата установлена: {field_key} = {date_str}")


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
    logger.info(f"Склад выбран: {warehouse_name}")


def click_generate():
    """Нажимает кнопку 'Сформировать'"""
    coords = UI_ELEMENTS["btn_generate"]
    pyautogui.click(coords["x"], coords["y"])
    logger.info("Нажата кнопка 'Сформировать'")


def wait_for_report(timeout: int = 90, check_interval: float = 3.0) -> bool:
    """
    Ждёт формирования отчёта.
    Просто ждём фиксированное время — отчёт обычно формируется за 10-30 сек.
    """
    logger.info(f"Ожидаю формирования отчёта (до {timeout} сек)...")

    # Простой подход: ждём UI_TIMEOUT_REPORT секунд
    # Более сложная проверка по пикселям ненадёжна через RDP
    time.sleep(UI_TIMEOUT_REPORT)

    # Дополнительная проверка: делаем скриншот и смотрим
    # есть ли данные в области таблицы
    try:
        screenshot = pyautogui.screenshot(
            region=(400, 250, 300, 100)
        )
        pixels = list(screenshot.getdata())
        non_white = sum(1 for p in pixels if p[0] < 240 or p[1] < 240 or p[2] < 240)
        if non_white > 200:
            logger.info("Отчёт сформирован (обнаружены данные в области таблицы)")
            return True
    except Exception:
        pass

    # Если проверка пикселей не дала однозначного результата —
    # всё равно возвращаем True (попробуем экспорт)
    logger.info("Предполагаем что отчёт сформирован (по таймауту)")
    return True


def export_to_excel(warehouse_name: str, date_str: str) -> str | None:
    """
    Экспортирует текущий отчёт в Excel через Ctrl+S.

    В RDP нажатие Ctrl+S попадает в 1С (если RDP-окно активно).
    Файл сохраняется на УДАЛЁННОМ сервере, поэтому нужна общая/сетевая папка.

    ВАЖНО: Сохраняем на сетевой диск или в папку, доступную с локального ПК.
    Если RDP-сервер и локальный ПК не имеют общих дисков — 
    используем перенаправленный диск (\\tsclient\C\...).
    """
    # Путь через перенаправленный диск RDP (\\tsclient\C\путь)
    # Это позволяет 1С сохранить файл прямо на локальный ПК
    safe_name = warehouse_name.replace(" ", "_")
    safe_date = date_str.replace(".", "-")
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"stock_{safe_name}_{safe_date}_{timestamp}.xlsx"

    # Локальный путь (где файл окажется на нашем ПК)
    local_path = str(EXPORT_DIR / filename)

    # Путь для ввода в диалог "Сохранить как" внутри RDP
    # \\tsclient\C — это диск C: локального ПК, видимый из RDP
    rdp_save_path = f"\\\\tsclient\\C\\Users\\dhkgh\\vgbxtgfxd-gmail.com\\1c-stock-bot\\exports\\{filename}"

    try:
        # Ctrl+S — открывает диалог "Сохранить как" в 1С
        pyautogui.hotkey("ctrl", "s")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Диалог открылся. Поле имени файла активно.
        # Очищаем и вводим путь
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.3)

        # Вводим путь через tsclient (сохраняет на локальный ПК)
        type_text_clipboard(rdp_save_path)
        time.sleep(1)

        # Нажимаем "Сохранить" (Enter)
        pyautogui.press("enter")
        time.sleep(UI_TIMEOUT_MEDIUM)

        # Если 1С спрашивает подтверждение — подтверждаем
        pyautogui.press("enter")
        time.sleep(UI_TIMEOUT_SHORT)

        # Проверяем что файл появился локально
        if Path(local_path).exists():
            logger.info(f"Excel сохранён через tsclient: {local_path}")
            return local_path

        # Если tsclient не сработал — возможно файл сохранился с другим расширением
        # Проверяем .mxl
        mxl_local = local_path.replace(".xlsx", ".mxl")
        if Path(mxl_local).exists():
            logger.warning(f"Сохранено как .mxl: {mxl_local}")
            return mxl_local

        # Если ничего нет — возможно tsclient недоступен
        logger.error("Файл не появился. Проверь что в RDP включено перенаправление дисков.")
        take_screenshot("export_no_file")
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


if __name__ == "__main__":
    # Тест: проверяем что RDP-окно находится
    print("Поиск RDP-окна...")
    win = find_rdp_window()
    if win:
        print(f"Найдено: '{win.title}' [{win.width}x{win.height}] at ({win.left},{win.top})")
    else:
        print("RDP-окно не найдено. Открой RDP-сессию и попробуй снова.")
        print("\nВсе окна:")
        for w in gw.getAllWindows():
            if w.title.strip():
                print(f"  '{w.title}'")
