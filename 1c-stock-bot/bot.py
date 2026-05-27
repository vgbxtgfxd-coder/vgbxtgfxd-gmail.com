"""
Telegram-бот для запроса складских остатков из 1С
"""
import asyncio
import logging
from datetime import date

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ALLOWED_USERS, WAREHOUSES, EXPORT_DIR
from automation import generate_1c_report
from parser_excel import parse_stock_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_authorized(user_id: int) -> bool:
    """Проверка что пользователь в белом списке"""
    if not ALLOWED_USERS:
        return True  # если список пуст — доступ всем
    return user_id in ALLOWED_USERS


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_authorized(message.from_user.id):
        return
    text = (
        "📦 <b>Бот складских остатков 1С</b>\n\n"
        "Команды:\n"
        "/stock <склад> — получить полный отчёт по складу\n"
        "/stock_date <склад> <дата> — отчёт за конкретную дату\n"
        "/warehouses — список доступных складов\n"
        "/status — проверить состояние 1С\n\n"
        "Примеры:\n"
        "<code>/stock томилино</code>\n"
        "<code>/stock_date дедовск 27.05.2026</code>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("warehouses"))
async def cmd_warehouses(message: types.Message):
    if not is_authorized(message.from_user.id):
        return
    lines = ["<b>Доступные склады:</b>\n"]
    seen = set()
    for key, name in WAREHOUSES.items():
        if name not in seen:
            lines.append(f"• <code>{key}</code> → {name}")
            seen.add(name)
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@dp.message(Command("stock"))
async def cmd_stock(message: types.Message):
    if not is_authorized(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Укажи склад.\nПример: <code>/stock томилино</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    warehouse_key = args[1].strip().lower()
    warehouse_name = WAREHOUSES.get(warehouse_key)

    if not warehouse_name:
        await message.answer(
            f"Склад '<code>{args[1]}</code>' не найден.\n"
            f"Используй /warehouses для списка.",
            parse_mode=ParseMode.HTML,
        )
        return

    today = date.today().strftime("%d.%m.%Y")
    await message.answer(
        f"⏳ Формирую отчёт...\n"
        f"Склад: {warehouse_name}\n"
        f"Дата: {today}",
        parse_mode=ParseMode.HTML,
    )

    try:
        excel_path = await asyncio.to_thread(
            generate_1c_report, warehouse_name, today, today
        )

        if excel_path is None:
            await message.answer("❌ Ошибка формирования отчёта в 1С. Проверь логи.")
            return

        # Парсим Excel
        stock_data = parse_stock_report(excel_path)

        if not stock_data:
            await message.answer("⚠️ Отчёт сформирован, но данные пусты.")
            return

        # Формируем текстовый отчёт
        report_text = format_stock_report(stock_data, warehouse_name, today)

        # Отправляем текст (разбиваем если длинный)
        for chunk in split_message(report_text):
            await message.answer(chunk, parse_mode=ParseMode.HTML)

        # Отправляем Excel-файл
        doc = FSInputFile(excel_path)
        await message.answer_document(doc, caption=f"📎 {warehouse_name} — {today}")

    except Exception as e:
        logger.exception("Ошибка при формировании отчёта")
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("stock_date"))
async def cmd_stock_date(message: types.Message):
    if not is_authorized(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "Формат: <code>/stock_date склад ДД.ММ.ГГГГ</code>\n"
            "Пример: <code>/stock_date томилино 27.05.2026</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    warehouse_key = args[1].strip().lower()
    date_str = args[2].strip()
    warehouse_name = WAREHOUSES.get(warehouse_key)

    if not warehouse_name:
        await message.answer(
            f"Склад '<code>{args[1]}</code>' не найден.\n/warehouses для списка.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Валидация даты
    try:
        parts = date_str.split(".")
        if len(parts) != 3 or len(parts[0]) != 2 or len(parts[1]) != 2:
            raise ValueError("bad format")
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат даты. Используй ДД.ММ.ГГГГ")
        return

    await message.answer(
        f"⏳ Формирую отчёт...\nСклад: {warehouse_name}\nДата: {date_str}",
        parse_mode=ParseMode.HTML,
    )

    try:
        excel_path = await asyncio.to_thread(
            generate_1c_report, warehouse_name, date_str, date_str
        )

        if excel_path is None:
            await message.answer("❌ Ошибка формирования отчёта в 1С.")
            return

        stock_data = parse_stock_report(excel_path)

        if not stock_data:
            await message.answer("⚠️ Отчёт пуст.")
            return

        report_text = format_stock_report(stock_data, warehouse_name, date_str)
        for chunk in split_message(report_text):
            await message.answer(chunk, parse_mode=ParseMode.HTML)

        doc = FSInputFile(excel_path)
        await message.answer_document(doc, caption=f"📎 {warehouse_name} — {date_str}")

    except Exception as e:
        logger.exception("Ошибка при формировании отчёта")
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if not is_authorized(message.from_user.id):
        return
    # Простая проверка — можно расширить
    await message.answer(
        "✅ Бот работает.\n"
        "RDP-сессия: предполагается открытой.\n"
        "Для проверки 1С используй /stock с любым складом.",
        parse_mode=ParseMode.HTML,
    )


def format_stock_report(stock_data: list[dict], warehouse: str, date_str: str) -> str:
    """Форматирует данные остатков в текстовый отчёт"""
    lines = [f"<b>📦 Остатки: {warehouse}</b>", f"<i>Дата: {date_str}</i>\n"]
    lines.append("<pre>")
    lines.append(f"{'Номенклатура':<40} {'Ост.(ед)':<10} {'Ост.(кг)':<10} {'Ост.(м)':<10}")
    lines.append("─" * 70)

    for item in stock_data:
        name = item.get("name", "")[:40]
        qty = item.get("end_qty", "")
        kg = item.get("end_kg", "")
        m = item.get("end_m", "")
        lines.append(f"{name:<40} {qty:<10} {kg:<10} {m:<10}")

    lines.append("</pre>")
    lines.append(f"\n<i>Всего позиций: {len(stock_data)}</i>")
    return "\n".join(lines)


def split_message(text: str, max_len: int = 4000) -> list[str]:
    """Разбивает длинное сообщение на части для Telegram"""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Ищем последний перенос строки в пределах лимита
        cut = text[:max_len].rfind("\n")
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
