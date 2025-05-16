import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Запись логов в файл
        logging.StreamHandler()  # Вывод логов в консоль
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация бота
API_TOKEN = os.getenv('BotToken')
if not API_TOKEN:
    logger.critical("Не задан API_TOKEN! Завершение работы.")
    exit(1)

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище валют
currencies = {}


# Машина состояний
class CurrencyStates(StatesGroup):
    waiting_for_currency_name = State()
    waiting_for_currency_rate = State()
    waiting_for_convert_currency = State()
    waiting_for_convert_amount = State()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запустил бота")
    await message.answer(
        "💰 Бот для работы с валютами:\n"
        "/save_currency - добавить курс\n"
        "/convert - конвертировать в рубли\n"
        "/list_currencies - список валют"
    )


@dp.message(Command('list_currencies'))
async def cmd_list_currencies(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил список валют")
    if not currencies:
        logger.warning("Попытка просмотра списка при отсутствии валют")
        await message.answer("ℹ️ Нет сохранённых валют. Добавьте через /save_currency")
        return

    currencies_list = "\n".join(f"• {k}: {v} RUB" for k, v in currencies.items())
    logger.debug(f"Сформирован список валют: {currencies}")
    await message.answer(f"📊 Список валют:\n{currencies_list}")


@dp.message(Command('save_currency'))
async def cmd_save_currency(message: Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} начал сохранение валюты")
    await message.answer("Введите название валюты (например, USD):")
    await state.set_state(CurrencyStates.waiting_for_currency_name)


@dp.message(CurrencyStates.waiting_for_currency_name)
async def process_currency_name(message: Message, state: FSMContext):
    currency = message.text.upper()
    logger.debug(f"Получено название валюты: {currency}")
    await state.update_data(currency_name=currency)
    await message.answer(f"Введите курс {currency} к рублю:")
    await state.set_state(CurrencyStates.waiting_for_currency_rate)


@dp.message(CurrencyStates.waiting_for_currency_rate)
async def process_currency_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(',', '.'))
        if rate <= 0:
            logger.warning(f"Некорректный курс: {message.text}")
            await message.answer("❌ Курс должен быть > 0!")
            return

        data = await state.get_data()
        currency = data['currency_name']
        currencies[currency] = rate
        logger.info(f"Сохранена валюта: {currency} = {rate}")
        await message.answer(f"✅ Курс {currency} = {rate} RUB сохранён!")
        await state.clear()

    except ValueError as e:
        logger.error(f"Ошибка преобразования курса: {message.text}. {str(e)}")
        await message.answer("🚫 Ошибка: введите число!")


@dp.message(Command('convert'))
async def cmd_convert(message: Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} начал конвертацию")
    if not currencies:
        logger.warning("Попытка конвертации при отсутствии валют")
        await message.answer("ℹ️ Сначала добавьте валюту через /save_currency")
        return
    await message.answer("Введите валюту для конвертации:")
    await state.set_state(CurrencyStates.waiting_for_convert_currency)


@dp.message(CurrencyStates.waiting_for_convert_currency)
async def process_convert_currency(message: Message, state: FSMContext):
    currency = message.text.upper()
    if currency not in currencies:
        logger.warning(f"Запрошена несуществующая валюта: {currency}")
        await message.answer(f"❌ Валюта {currency} не найдена. Доступные: {', '.join(currencies.keys())}")
        await state.clear()
        return

    await state.update_data(currency=currency)
    logger.debug(f"Выбрана валюта для конвертации: {currency}")
    await message.answer(f"Введите сумму в {currency}:")
    await state.set_state(CurrencyStates.waiting_for_convert_amount)


@dp.message(CurrencyStates.waiting_for_convert_amount)
async def process_convert_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            logger.warning(f"Некорректная сумма: {message.text}")
            await message.answer("❌ Сумма должна быть > 0!")
            return

        data = await state.get_data()
        currency = data['currency']
        rate = currencies[currency]
        result = amount * rate
        logger.info(f"Конвертация: {amount} {currency} = {result} RUB")
        await message.answer(f"💱 {amount} {currency} = {result:.2f} RUB")
        await state.clear()

    except ValueError as e:
        logger.error(f"Ошибка преобразования суммы: {message.text}. {str(e)}")
        await message.answer("🚫 Ошибка: введите число!")


async def main():
    logger.info("Запуск бота...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Ошибка при работе бота: {str(e)}")
    finally:
        logger.info("Бот остановлен")


if __name__ == '__main__':
    asyncio.run(main())