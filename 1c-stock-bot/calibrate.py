"""
Калибровка UI-элементов 1С (через RDP, на слух).

5 элементов по порядку:
  1. "Склад" в левом меню
  2. "Дополнительные отчёты"
  3. "Выполнить" (в окне доп.отчётов)
  4. "Сформировать" (в форме отчёта)
  5. (не нужен для теста, но на будущее — поле склада)

Звуковые сигналы:
  1 бип  = ГОТОВЬСЯ (наводи мышь на следующий элемент)
  8 сек  = время навести
  2 бипа = ЗАХВАЧЕНО

Использование:
    python calibrate.py
"""
import time
import sys
import os

try:
    import pyautogui
except ImportError:
    print("Установи: pip install pyautogui")
    sys.exit(1)

try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False


def beep_ready():
    """1 бип = ГОТОВЬСЯ"""
    if HAS_SOUND:
        winsound.Beep(800, 300)


def beep_captured():
    """2 бипа = ЗАХВАЧЕНО"""
    if HAS_SOUND:
        winsound.Beep(1200, 400)
        time.sleep(0.1)
        winsound.Beep(1200, 400)


def beep_start():
    """3 быстрых бипа = СТАРТ"""
    if HAS_SOUND:
        for _ in range(3):
            winsound.Beep(600, 150)
            time.sleep(0.1)


def beep_done():
    """Мелодия = ГОТОВО"""
    if HAS_SOUND:
        for freq in [800, 1000, 1200, 1500]:
            winsound.Beep(freq, 200)
            time.sleep(0.05)


def main():
    print("=" * 60)
    print("  КАЛИБРОВКА 1С (через RDP, на слух)")
    print("=" * 60)
    print()
    print("  Порядок элементов (запомни!):")
    print()
    print('    1. "Склад" — в ЛЕВОМ МЕНЮ 1С')
    print('    2. "Дополнительные отчёты" — ссылка в разделе')
    print('    3. "Выполнить" — кнопка в окне доп.отчётов')
    print('    4. "Сформировать" — кнопка в форме отчёта')
    print()
    print("  Сигналы:")
    print("    1 бип  = наводи мышь (8 секунд)")
    print("    2 бипа = захвачено, жди следующий")
    print()
    print("  ВАЖНО: после элемента 3 (Выполнить) откроется")
    print("  форма отчёта — поэтому перед элементом 4 будет")
    print("  пауза 10 сек чтобы форма загрузилась.")
    print()
    input("  Запомнил? Жми Enter, потом переключайся на RDP...")
    print()
    print("  15 секунд до старта — переключайся на RDP!")

    for i in range(15, 0, -1):
        print(f"\r  {i:2d} сек...  ", end="", flush=True)
        time.sleep(1)
    print("\r  СТАРТ!        ")

    beep_start()
    time.sleep(1)

    targets = [
        ("menu_sklad", 'Меню "Склад" (слева)', 8, 3),
        ("btn_dop_reports", '"Дополнительные отчёты"', 8, 3),
        ("btn_execute", 'Кнопка "Выполнить"', 8, 10),  # 10 сек после — ждём загрузку формы
        ("btn_generate", 'Кнопка "Сформировать"', 8, 3),
    ]

    results = {}

    for i, (key, label, wait_time, pause_after) in enumerate(targets, 1):
        # Сигнал "готовься"
        beep_ready()

        # Время на наведение мыши
        time.sleep(wait_time)

        # Захват
        pos = pyautogui.position()
        results[key] = {"x": pos.x, "y": pos.y}

        # Сигнал "захвачено"
        beep_captured()
        print(f"  [{i}/4] {label}: x={pos.x}, y={pos.y} ✓")

        # Пауза перед следующим
        time.sleep(pause_after)

    # Финал
    beep_done()

    print()
    print("=" * 60)
    print("  РЕЗУЛЬТАТ")
    print("=" * 60)
    print()
    print("UI_ELEMENTS = {")
    for key, coords in results.items():
        print(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},')
    print("}")

    # Сохраняем
    with open("calibration_result.txt", "w", encoding="utf-8") as f:
        f.write("UI_ELEMENTS = {\n")
        for key, coords in results.items():
            f.write(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n')
        f.write("}\n")

    # Обновляем config.py
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            marker = "UI_ELEMENTS = {"
            idx = content.find(marker)
            if idx != -1:
                search_from = idx + len(marker)
                brace_count = 1
                end_idx = search_from
                while end_idx < len(content) and brace_count > 0:
                    if content[end_idx] == "{":
                        brace_count += 1
                    elif content[end_idx] == "}":
                        brace_count -= 1
                    end_idx += 1

                new_block = "UI_ELEMENTS = {\n"
                for key, coords in results.items():
                    new_block += f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n'
                new_block += "}"

                new_content = content[:idx] + new_block + content[end_idx:]
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                print("\n✓ config.py обновлён!")
            else:
                print("\n⚠ UI_ELEMENTS не найден в config.py")
        except Exception as e:
            print(f"\n⚠ Ошибка: {e}")

    print("\nГотово! Перезапусти бота: python bot.py")


if __name__ == "__main__":
    main()
