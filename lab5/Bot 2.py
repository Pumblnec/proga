import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import asyncpg

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Конфигурация бота
API_TOKEN = os.getenv('botToken')
if not API_TOKEN:
    logger.critical("Не задан API_TOKEN! Завершение работы.")
    exit(1)

# Конфигурация базы данных
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Машина состояний
class CurrencyStates(StatesGroup):
    waiting_for_currency_name = State()
    waiting_for_currency_rate = State()
    waiting_for_convert_currency = State()
    waiting_for_convert_amount = State()
    waiting_for_currency_to_delete = State()
    waiting_for_currency_to_update = State()
    waiting_for_new_currency_rate = State()

async def create_db_connection():
    return await asyncpg.connect(**DB_CONFIG)

async def init_db():
    conn = None
    try:
        conn = await create_db_connection()
        await conn.execute("SELECT 1 FROM currencies LIMIT 1")
        await conn.execute("SELECT 1 FROM admins LIMIT 1")
        logger.info("Подключение к базе данных успешно")
    except Exception as e:
        logger.error(f"Ошибка при проверке таблиц: {str(e)}")
        exit(1)
    finally:
        if conn:
            await conn.close()

async def is_admin(chat_id: str) -> bool:
    conn = None
    try:
        conn = await create_db_connection()
        return await conn.fetchval("SELECT 1 FROM admins WHERE chat_id = $1", str(chat_id)) is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке администратора: {str(e)}")
        return False
    finally:
        if conn:
            await conn.close()

async def get_currencies():
    conn = None
    try:
        conn = await create_db_connection()
        records = await conn.fetch("SELECT currency_name, rate FROM currencies")
        return {record['currency_name']: record['rate'] for record in records}
    except Exception as e:
        logger.error(f"Ошибка при получении валют: {str(e)}")
        return {}
    finally:
        if conn:
            await conn.close()

async def add_currency(name: str, rate: float) -> bool:
    conn = None
    try:
        conn = await create_db_connection()
        await conn.execute("INSERT INTO currencies (currency_name, rate) VALUES ($1, $2)", name, rate)
        return True
    except asyncpg.UniqueViolationError:
        logger.warning(f"Валюта {name} уже существует")
        return False
    except Exception as e:
        logger.error(f"Ошибка при добавлении валюты: {str(e)}")
        return False
    finally:
        if conn:
            await conn.close()

async def delete_currency(name: str) -> bool:
    conn = None
    try:
        conn = await create_db_connection()
        return await conn.execute("DELETE FROM currencies WHERE currency_name = $1", name) != "DELETE 0"
    except Exception as e:
        logger.error(f"Ошибка при удалении валюты: {str(e)}")
        return False
    finally:
        if conn:
            await conn.close()

async def update_currency_rate(name: str, new_rate: float) -> bool:
    conn = None
    try:
        conn = await create_db_connection()
        return await conn.execute("UPDATE currencies SET rate = $1 WHERE currency_name = $2", new_rate, name) != "UPDATE 0"
    except Exception as e:
        logger.error(f"Ошибка при обновлении курса: {str(e)}")
        return False
    finally:
        if conn:
            await conn.close()

def get_manage_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Добавить валюту"),
        KeyboardButton(text="Удалить валюту"),
        KeyboardButton(text="Изменить курс валюты")
    )
    builder.row(KeyboardButton(text="Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_dev_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Проверить соединение с БД")],
            [KeyboardButton(text="Логи бота")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )

async def set_commands_for_user(user_id: int):
    commands = [
        types.BotCommand(command="start", description="Запустить бота"),
        types.BotCommand(command="get_currencies", description="Список всех валют"),
        types.BotCommand(command="convert", description="Конвертировать в рубли"),
    ]
    if await is_admin(str(user_id)):
        commands.extend([
            types.BotCommand(command="manage_currency", description="Управление валютами (админ)"),
            types.BotCommand(command="dev_menu", description="Меню разработчика (админ)")
        ])
    await bot.set_my_commands(commands)

# Команды

@dp.message(Command('start'))
async def cmd_start(message: Message):
    await set_commands_for_user(message.from_user.id)
    if await is_admin(str(message.from_user.id)):
        await message.answer(
            "💰 Бот для работы с валютами (админ-режим):\n"
            "/get_currencies - список всех валют\n"
            "/convert - конвертировать в рубли\n"
            "/manage_currency - управление валютами\n"
            "/dev_menu - меню разработчика"
        )
    else:
        await message.answer(
            "💰 Бот для работы с валютами:\n"
            "/get_currencies - список всех валют\n"
            "/convert - конвертировать в рубли"
        )

@dp.message(Command('get_currencies'))
async def cmd_get_currencies(message: Message):
    try:
        currencies = await get_currencies()
        if not currencies:
            await message.answer("ℹ️ В базе нет сохранённых валют")
            return
        await message.answer("📊 Актуальные курсы валют:\n" +
            "\n".join(f"• {c}: {r} RUB" for c, r in sorted(currencies.items())))
    except Exception as e:
        logger.error(f"Ошибка при получении списка валют: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при получении курсов валют")

@dp.message(Command('convert'))
async def cmd_convert(message: Message, state: FSMContext):
    try:
        currencies = await get_currencies()
        if not currencies:
            await message.answer("ℹ️ Нет доступных валют для конвертации")
            return
        await message.answer(f"Введите название валюты (например, USD, EUR).\nДоступные валюты: {', '.join(currencies.keys())}")
        await state.set_state(CurrencyStates.waiting_for_convert_currency)
    except Exception as e:
        logger.error(f"Ошибка при запуске конвертации: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при запуске конвертации")

@dp.message(CurrencyStates.waiting_for_convert_currency)
async def process_convert_currency(message: Message, state: FSMContext):
    currency = message.text.strip().upper()
    currencies = await get_currencies()
    if currency not in currencies:
        await message.answer(f"❌ Валюта '{currency}' не найдена.\nДоступные валюты: {', '.join(currencies.keys())}")
        return
    await state.update_data(currency=currency)
    await message.answer(f"Введите сумму в {currency} для конвертации в рубли:")
    await state.set_state(CurrencyStates.waiting_for_convert_amount)

@dp.message(CurrencyStates.waiting_for_convert_amount)
async def process_convert_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        data = await state.get_data()
        currency = data['currency']
        rate = (await get_currencies())[currency]
        result = amount * float(rate)
        await message.answer(f"💱 Результат конвертации:\n{amount:.2f} {currency} = {result:.2f} RUB\nКурс: 1 {currency} = {rate} RUB")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число!")
    except Exception as e:
        logger.error(f"Ошибка при конвертации: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при конвертации")
    finally:
        await state.clear()

# Панель админа

@dp.message(Command('manage_currency'))
async def cmd_manage_currency(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id)):
        await message.answer("Нет доступа к команде")
        return
    await message.answer("Управление валютами:", reply_markup=get_manage_keyboard())

@dp.message(lambda message: message.text == "Добавить валюту")
async def add_currency_handler(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id)):
        return
    await message.answer("Введите название валюты:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CurrencyStates.waiting_for_currency_name)

@dp.message(CurrencyStates.waiting_for_currency_name)
async def process_currency_name(message: Message, state: FSMContext):
    currency = message.text.upper()
    if currency in await get_currencies():
        await message.answer("Данная валюта уже существует")
        await state.clear()
        return
    await state.update_data(currency_name=currency)
    await message.answer(f"Введите курс {currency} к рублю:")
    await state.set_state(CurrencyStates.waiting_for_currency_rate)

@dp.message(CurrencyStates.waiting_for_currency_rate)
async def process_currency_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(',', '.'))
        if rate <= 0:
            await message.answer("❌ Курс должен быть > 0!")
            return
        data = await state.get_data()
        await message.answer(f"✅ Валюта {data['currency_name']} успешно добавлена"
            if await add_currency(data['currency_name'], rate) else "❌ Ошибка при добавлении валюты")
    except ValueError:
        await message.answer("🚫 Ошибка: введите число!")
    finally:
        await state.clear()

@dp.message(lambda message: message.text == "Удалить валюту")
async def delete_currency_handler(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id)):
        return
    await message.answer("Введите название валюты для удаления:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CurrencyStates.waiting_for_currency_to_delete)

@dp.message(CurrencyStates.waiting_for_currency_to_delete)
async def process_currency_to_delete(message: Message, state: FSMContext):
    currency = message.text.upper()
    await message.answer(f"✅ Валюта {currency} успешно удалена"
        if await delete_currency(currency) else f"❌ Валюта {currency} не найдена")
    await state.clear()

@dp.message(lambda message: message.text == "Изменить курс валюты")
async def update_currency_handler(message: Message, state: FSMContext):
    if not await is_admin(str(message.from_user.id)):
        return
    await message.answer("Введите название валюты для изменения:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(CurrencyStates.waiting_for_currency_to_update)

@dp.message(CurrencyStates.waiting_for_currency_to_update)
async def process_currency_to_update(message: Message, state: FSMContext):
    await state.update_data(currency_name=message.text.upper())
    await message.answer(f"Введите новый курс {message.text.upper()} к рублю:")
    await state.set_state(CurrencyStates.waiting_for_new_currency_rate)

@dp.message(CurrencyStates.waiting_for_new_currency_rate)
async def process_new_currency_rate(message: Message, state: FSMContext):
    try:
        new_rate = float(message.text.replace(',', '.'))
        if new_rate <= 0:
            await message.answer("❌ Курс должен быть > 0!")
            return
        data = await state.get_data()
        currency = data['currency_name']
        await message.answer(f"✅ Курс {currency} успешно обновлён"
            if await update_currency_rate(currency, new_rate) else f"❌ Валюта {currency} не найдена")
    except ValueError:
        await message.answer("🚫 Ошибка: введите число!")
    finally:
        await state.clear()


# Обработчики

@dp.message(lambda message: message.text == "Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено", reply_markup=types.ReplyKeyboardRemove())

# Запуск

async def main():
    await init_db()
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запустить бота"),
        types.BotCommand(command="get_currencies", description="Список всех валют"),
        types.BotCommand(command="convert", description="Конвертировать в рубли"),
    ])
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
