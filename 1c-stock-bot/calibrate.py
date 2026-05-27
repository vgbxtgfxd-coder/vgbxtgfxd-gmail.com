"""
Утилита калибровки координат UI-элементов 1С.
Версия с таймером — не нужно нажимать Enter.

Запускай на рабочем ПК при открытом окне 1С с отчётом.
Наводи мышь на элемент → ждёшь 5 секунд → координаты сохраняются.

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


def main():
    print("=" * 60)
    print("  КАЛИБРОВКА UI-ЭЛЕМЕНТОВ 1С (режим таймера)")
    print("  Отчёт: ОСВ по номенклатуре и заказам")
    print("=" * 60)
    print()
    print("Как работает:")
    print("  1. Для каждого элемента у тебя 5 секунд")
    print("  2. Наведи мышь на нужный элемент в 1С")
    print("  3. Когда таймер дойдёт до 0 — координаты запомнятся")
    print("  4. Прозвучит сигнал — можно переходить к следующему")
    print()
    print("Переключись на RDP с 1С (полный экран — ОК)")
    print()

    # Начальная пауза чтобы переключиться на RDP
    print(">>> СТАРТ через 10 секунд — переключись на 1С! <<<")
    for i in range(10, 0, -1):
        print(f"\r    Начало через {i} сек...  ", end="", flush=True)
        time.sleep(1)
    print("\r    ПОЕХАЛИ!                      ")
    print()

    targets = [
        ("date_start", "Поле ДАТЫ НАЧАЛА (левое поле с датой, например 27.05.2026)"),
        ("date_end", "Поле ДАТЫ КОНЦА (правое поле с датой)"),
        ("warehouse_checkbox", "ЧЕКБОКС 'Склад' (зелёная галочка слева от поля склада)"),
        ("warehouse_field", "ПОЛЕ ВВОДА СКЛАДА (текстовое поле, где написано 'склад Томилино')"),
        ("btn_generate", "КНОПКА 'Сформировать' (зелёная кнопка)"),
        ("nomenclature_field", "ПОЛЕ 'Номенклатура труб' (текстовое поле фильтра)"),
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

        # Пауза 2 секунды между элементами чтобы перевести мышь
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
    print("Скопируй значения в config.py (замени блок UI_ELEMENTS)")
    print()

    # Автоматическое обновление config.py
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()

            # Ищем блок UI_ELEMENTS и заменяем
            start_marker = "UI_ELEMENTS = {"
            end_marker = "}"

            start_idx = config_content.find(start_marker)
            if start_idx != -1:
                # Находим закрывающую скобку блока
                search_from = start_idx + len(start_marker)
                brace_count = 1
                end_idx = search_from
                while end_idx < len(config_content) and brace_count > 0:
                    if config_content[end_idx] == "{":
                        brace_count += 1
                    elif config_content[end_idx] == "}":
                        brace_count -= 1
                    end_idx += 1

                # Формируем новый блок
                new_block = "UI_ELEMENTS = {\n"
                for key, coords in results.items():
                    new_block += f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n'
                new_block += "}"

                # Заменяем
                new_config = config_content[:start_idx] + new_block + config_content[end_idx:]

                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_config)

                print("✓ config.py обновлён автоматически!")
            else:
                print("⚠ Не удалось найти UI_ELEMENTS в config.py — обнови вручную")

        except Exception as e:
            print(f"⚠ Ошибка обновления config.py: {e}")
            print("  Обнови вручную из calibration_result.txt")

    print("\nГотово! Можно запускать бота: python bot.py")


if __name__ == "__main__":
    main()
