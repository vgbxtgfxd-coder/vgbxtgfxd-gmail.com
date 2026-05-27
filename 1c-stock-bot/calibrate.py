"""
Утилита калибровки координат UI-элементов 1С (через RDP).
Версия с таймером — не нужно нажимать Enter.

Работает так:
1. Запускаешь скрипт
2. 10 секунд на переключение к RDP с 1С (полноэкранный режим — ОК)
3. Для каждого элемента 5 секунд — наводишь мышь, ждёшь
4. Координаты сохраняются автоматически в config.py

Использование:
    python calibrate.py
"""
import time
import sys
import os

try:
    import pyautogui
except ImportError:
    print("Установи pyautogui: pip install pyautogui")
    sys.exit(1)

try:
    import pygetwindow as gw
except ImportError:
    gw = None


def countdown(seconds: int, label: str):
    """Обратный отсчёт с выводом в одну строку"""
    for i in range(seconds, 0, -1):
        print(f"\r    [{label}] Наведи мышь → захват через {i} сек...", end="", flush=True)
        time.sleep(1)
    print(f"\r    [{label}] Захват!                                    ", flush=True)


def beep():
    """Звуковой сигнал при захвате (Windows)"""
    try:
        import winsound
        winsound.Beep(1000, 200)
    except Exception:
        pass


def find_rdp_window():
    """Показывает найденное RDP-окно для проверки"""
    if gw is None:
        return None
    all_windows = gw.getAllWindows()
    for win in all_windows:
        title = win.title.lower()
        if any(kw in title for kw in ["удалённый рабочий стол", "удаленный рабочий стол", "remote desktop"]):
            return win
    for win in all_windows:
        if "РГК" in win.title or "ИПК" in win.title:
            return win
    return None


def main():
    print("=" * 60)
    print("  КАЛИБРОВКА UI-ЭЛЕМЕНТОВ 1С (через RDP)")
    print("  Отчёт: ОСВ по номенклатуре и заказам")
    print("=" * 60)
    print()

    # Проверяем RDP-окно
    rdp = find_rdp_window()
    if rdp:
        print(f"  RDP-окно найдено: '{rdp.title}'")
    else:
        print("  ⚠ RDP-окно не найдено автоматически — это ОК,")
        print("    просто переключись на RDP вручную.")
    print()

    print("Как работает:")
    print("  1. Переключись на RDP с открытой 1С")
    print("  2. Для каждого элемента — 5 секунд наводишь мышь")
    print("  3. Звуковой сигнал = координаты захвачены")
    print("  4. config.py обновится автоматически")
    print()

    # Начальная пауза
    print(">>> СТАРТ через 10 секунд — переключись на RDP с 1С! <<<")
    for i in range(10, 0, -1):
        print(f"\r    Начало через {i} сек...  ", end="", flush=True)
        time.sleep(1)
    print("\r    ПОЕХАЛИ!                      ")
    print()

    targets = [
        ("date_start", "Поле ДАТЫ НАЧАЛА (где написано '27.05.2026' слева)"),
        ("date_end", "Поле ДАТЫ КОНЦА (правая дата)"),
        ("warehouse_checkbox", "ЧЕКБОКС 'Склад' (зелёная галочка)"),
        ("warehouse_field", "ПОЛЕ ВВОДА СКЛАДА (текст 'склад Томилино')"),
        ("btn_generate", "КНОПКА 'Сформировать'"),
        ("nomenclature_field", "ПОЛЕ 'Номенклатура труб'"),
    ]

    results = {}

    for i, (key, label) in enumerate(targets, 1):
        print(f"  [{i}/{len(targets)}] {label}")
        countdown(5, key)

        pos = pyautogui.position()
        results[key] = {"x": pos.x, "y": pos.y}
        beep()
        print(f"    ✓ Сохранено: x={pos.x}, y={pos.y}")
        print()

        # Пауза между элементами
        if i < len(targets):
            time.sleep(2)

    # Вывод результата
    print()
    print("=" * 60)
    print("  РЕЗУЛЬТАТ КАЛИБРОВКИ")
    print("=" * 60)
    print()
    print("UI_ELEMENTS = {")
    for key, coords in results.items():
        print(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},')
    print("}")

    # Сохраняем в файл
    with open("calibration_result.txt", "w", encoding="utf-8") as f:
        f.write("UI_ELEMENTS = {\n")
        for key, coords in results.items():
            f.write(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n')
        f.write("}\n")

    print(f"\nРезультат сохранён в calibration_result.txt")

    # Автоматическое обновление config.py
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()

            start_marker = "UI_ELEMENTS = {"
            start_idx = config_content.find(start_marker)
            if start_idx != -1:
                # Находим конец блока
                search_from = start_idx + len(start_marker)
                brace_count = 1
                end_idx = search_from
                while end_idx < len(config_content) and brace_count > 0:
                    if config_content[end_idx] == "{":
                        brace_count += 1
                    elif config_content[end_idx] == "}":
                        brace_count -= 1
                    end_idx += 1

                # Новый блок
                new_block = "UI_ELEMENTS = {\n"
                for key, coords in results.items():
                    new_block += f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n'
                new_block += "}"

                new_config = config_content[:start_idx] + new_block + config_content[end_idx:]

                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_config)

                print("✓ config.py обновлён автоматически!")
            else:
                print("⚠ Не нашёл UI_ELEMENTS в config.py — обнови вручную")

        except Exception as e:
            print(f"⚠ Ошибка обновления config.py: {e}")

    print("\nГотово! Перезапусти бота: python bot.py")


if __name__ == "__main__":
    main()
