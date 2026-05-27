"""
Утилита калибровки координат UI-элементов 1С.

Запускай на рабочем ПК при открытом окне 1С с отчётом.
Наводи мышь на каждый элемент и нажимай Enter.
Результат скопируется в config.py.

Использование:
    python calibrate.py
"""
import time
import sys

try:
    import pyautogui
except ImportError:
    print("Установи pyautogui: pip install pyautogui")
    sys.exit(1)


def main():
    print("=" * 60)
    print("  КАЛИБРОВКА UI-ЭЛЕМЕНТОВ 1С")
    print("  Отчёт: ОСВ по номенклатуре и заказам")
    print("=" * 60)
    print()
    print("Инструкция:")
    print("  1. Открой 1С с отчётом ОСВ")
    print("  2. Для каждого элемента — наведи мышь и нажми Enter")
    print("  3. Для пропуска элемента — просто нажми Enter (оставит 0,0)")
    print("  4. Для выхода — введи 'q'")
    print()
    print("У тебя 5 секунд чтобы переключиться на 1С...")
    print()

    for i in range(5, 0, -1):
        print(f"  {i}...", end=" ", flush=True)
        time.sleep(1)
    print("\n")

    targets = [
        ("date_start", "Поле ДАТЫ НАЧАЛА (левое поле с датой)"),
        ("date_end", "Поле ДАТЫ КОНЦА (правое поле с датой)"),
        ("warehouse_checkbox", "ЧЕКБОКС 'Склад' (галочка)"),
        ("warehouse_field", "ПОЛЕ ВВОДА СКЛАДА (текстовое поле справа от чекбокса)"),
        ("btn_generate", "КНОПКА 'Сформировать'"),
        ("nomenclature_field", "ПОЛЕ 'Номенклатура труб' (для фильтрации)"),
    ]

    results = {}

    for key, label in targets:
        print(f"  → Наведи мышь на: {label}")
        inp = input("    [Enter — сохранить позицию | q — выход]: ").strip()

        if inp.lower() == "q":
            print("\nКалибровка прервана.")
            break

        pos = pyautogui.position()
        results[key] = {"x": pos.x, "y": pos.y}
        print(f"    ✓ Сохранено: x={pos.x}, y={pos.y}\n")

    # Калибровка экспорта
    print("\n--- Калибровка экспорта ---")
    print("Теперь нужны координаты для экспорта в Excel.")
    print("Если не знаешь — пропусти (нажми Enter).\n")

    export_targets = [
        ("btn_save", "Кнопка СОХРАНИТЬ (дискета/иконка) на панели отчёта"),
        ("menu_more", "Кнопка 'Ещё' (если есть) — меню экспорта"),
    ]

    for key, label in export_targets:
        print(f"  → Наведи мышь на: {label}")
        inp = input("    [Enter — сохранить | пустой Enter — пропустить | q — выход]: ").strip()

        if inp.lower() == "q":
            break

        pos = pyautogui.position()
        results[key] = {"x": pos.x, "y": pos.y}
        print(f"    ✓ Сохранено: x={pos.x}, y={pos.y}\n")

    # Вывод результата
    print("\n" + "=" * 60)
    print("  РЕЗУЛЬТАТ КАЛИБРОВКИ")
    print("=" * 60)
    print()
    print("Скопируй это в config.py (замени UI_ELEMENTS):\n")
    print("UI_ELEMENTS = {")
    for key, coords in results.items():
        print(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},')
    print("}")

    # Сохраняем в файл для удобства
    with open("calibration_result.txt", "w", encoding="utf-8") as f:
        f.write("UI_ELEMENTS = {\n")
        for key, coords in results.items():
            f.write(f'    "{key}": {{"x": {coords["x"]}, "y": {coords["y"]}}},\n')
        f.write("}\n")

    print(f"\nРезультат также сохранён в calibration_result.txt")
    print("Перенеси значения в config.py и перезапусти бота.")


if __name__ == "__main__":
    main()
