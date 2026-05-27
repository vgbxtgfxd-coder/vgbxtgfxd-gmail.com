"""
Утилита калибровки координат UI-элементов 1С (через RDP).

Работает со ЗВУКОВЫМИ СИГНАЛАМИ — можно находиться в полноэкранном RDP:

  1 короткий бип  = "ГОТОВЬСЯ, следующий элемент"
  Тишина 8 секунд = наводи мышь на нужный элемент
  2 длинных бипа  = "ЗАХВАЧЕНО, переходим к следующему"

Порядок элементов (запомни перед запуском):
  1. Поле ДАТЫ НАЧАЛА (левое)
  2. Поле ДАТЫ КОНЦА (правое)
  3. ЧЕКБОКС 'Склад' (зелёная галочка)
  4. ПОЛЕ ВВОДА СКЛАДА (где текст 'склад Томилино')
  5. КНОПКА 'Сформировать'
  6. ПОЛЕ 'Номенклатура труб'

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
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False


def beep_ready():
    """1 короткий бип = ГОТОВЬСЯ, наводи мышь"""
    if HAS_SOUND:
        winsound.Beep(800, 300)


def beep_captured():
    """2 длинных бипа = ЗАХВАЧЕНО"""
    if HAS_SOUND:
        winsound.Beep(1200, 400)
        time.sleep(0.1)
        winsound.Beep(1200, 400)


def beep_start():
    """3 быстрых бипа = СТАРТ калибровки (пошёл первый элемент)"""
    if HAS_SOUND:
        for _ in range(3):
            winsound.Beep(600, 150)
            time.sleep(0.1)


def beep_done():
    """Мелодия = ВСЁ ГОТОВО"""
    if HAS_SOUND:
        for freq in [800, 1000, 1200, 1500]:
            winsound.Beep(freq, 200)
            time.sleep(0.05)


def main():
    print("=" * 60)
    print("  КАЛИБРОВКА UI-ЭЛЕМЕНТОВ 1С (через RDP)")
    print("=" * 60)
    print()
    print("  Работает через ЗВУКОВЫЕ СИГНАЛЫ:")
    print("    1 бип        = ГОТОВЬСЯ (наводи мышь)")
    print("    8 сек тишина = время навести мышь")
    print("    2 бипа       = ЗАХВАЧЕНО")
    print()
    print("  Порядок элементов:")
    print("    1. Поле ДАТЫ НАЧАЛА (левое)")
    print("    2. Поле ДАТЫ КОНЦА (правое)")
    print("    3. ЧЕКБОКС 'Склад' (зелёная галочка)")
    print("    4. ПОЛЕ ВВОДА СКЛАДА (текст 'склад Томилино')")
    print("    5. КНОПКА 'Сформировать'")
    print("    6. ПОЛЕ 'Номенклатура труб'")
    print()
    print("  Запомнил порядок? Жми Enter когда готов.")
    input("  >>> ")
    print()
    print("  Переключайся на RDP! Через 15 секунд начнётся.")
    print("  (3 быстрых бипа = СТАРТ)")
    print()

    # Обратный отсчёт 15 секунд перед стартом
    for i in range(15, 0, -1):
        print(f"\r  Старт через {i:2d} сек...  ", end="", flush=True)
        time.sleep(1)
    print("\r  СТАРТ!                    ")

    # Сигнал старта
    beep_start()
    time.sleep(1)

    targets = [
        ("date_start", "Поле ДАТЫ НАЧАЛА"),
        ("date_end", "Поле ДАТЫ КОНЦА"),
        ("warehouse_checkbox", "ЧЕКБОКС 'Склад'"),
        ("warehouse_field", "ПОЛЕ ВВОДА СКЛАДА"),
        ("btn_generate", "КНОПКА 'Сформировать'"),
        ("nomenclature_field", "ПОЛЕ 'Номенклатура труб'"),
    ]

    results = {}

    for i, (key, label) in enumerate(targets, 1):
        # Сигнал "готовься" — 1 бип
        beep_ready()

        # 8 секунд на наведение мыши
        time.sleep(8)

        # Захват координат
        pos = pyautogui.position()
        results[key] = {"x": pos.x, "y": pos.y}

        # Сигнал "захвачено" — 2 бипа
        beep_captured()

        print(f"  [{i}/6] {label}: x={pos.x}, y={pos.y} ✓")

        # Пауза 3 секунды перед следующим
        time.sleep(3)

    # Финальный сигнал
    beep_done()

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

    # Автоматическое обновление config.py
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()

            start_marker = "UI_ELEMENTS = {"
            start_idx = config_content.find(start_marker)
            if start_idx != -1:
                search_from = start_idx + len(start_marker)
                brace_count = 1
                end_idx = search_from
                while end_idx < len(config_content) and brace_count > 0:
                    if config_content[end_idx] == "{":
                        brace_count += 1
                    elif config_content[end_idx] == "}":
                        brace_count -= 1
                    end_idx += 1

                new_block = "UI_ELEMENTS = {\n"
                for key, coords in results.items():
                    new_block += f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n'
                new_block += "}"

                new_config = config_content[:start_idx] + new_block + config_content[end_idx:]

                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_config)

                print("\n✓ config.py обновлён автоматически!")
            else:
                print("\n⚠ Не нашёл UI_ELEMENTS в config.py — обнови вручную")

        except Exception as e:
            print(f"\n⚠ Ошибка: {e}")

    print("\nГотово! Перезапусти бота: python bot.py")


if __name__ == "__main__":
    main()
