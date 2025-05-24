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
from datetime import datetime, timedelta
import aiohttp
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("finance_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}
CURRENCY_SERVICE_URL = os.getenv('CURRENCY_SERVICE_URL')

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Состояния FSM
class RegistrationState(StatesGroup):
    waiting_for_name = State()


class AddOperationState(StatesGroup):
    waiting_for_type = State()
    waiting_for_amount = State()
    waiting_for_date = State()


class ReportState(StatesGroup):
    waiting_for_currency = State()
    waiting_for_period = State()


class UpdateOperationState(StatesGroup):
    waiting_for_operation_id = State()
    waiting_for_new_amount = State()


# Подключение к бд БД
async def create_db_connection():
    """Создает подключение к базе данных"""
    return await asyncpg.connect(**DB_CONFIG)

async def init_db():
    conn = None
    try:
        conn = await create_db_connection()
        await conn.execute("SELECT 1 FROM users LIMIT 1")
        await conn.execute("SELECT 1 FROM operations LIMIT 1")
        logger.info("Подключение к базе данных успешно")
    except Exception as e:
        logger.error(f"Ошибка при проверке таблиц: {str(e)}")
        exit(1)
    finally:
        if conn:
            await conn.close()


# Работы с API
async def get_exchange_rate(currency: str) -> float:
    """Получает курс валюты от микросервиса"""
    if currency == 'RUB':
        return 1.0

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    f"{CURRENCY_SERVICE_URL}/rate?currency={currency}",
                    timeout=3
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['rate'])

                logger.warning(f"Не удалось получить курс валюты. Код ответа: {response.status}")
                return None

    except Exception as e:
        logger.error(f"Ошибка при получении курса валюты: {str(e)}")
        return None


# Клавиатуры
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Добавить операцию"),
        KeyboardButton(text="📊 Отчеты")
    )
    builder.row(
        KeyboardButton(text="ℹ️ Помощь")
    )
    return builder.as_markup(resize_keyboard=True)


def get_operation_type_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text="Доход"),
        KeyboardButton(text="Расход"),
        KeyboardButton(text="Отмена")
    )
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_currency_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text="RUB"),
        KeyboardButton(text="USD"),
        KeyboardButton(text="EUR"),
        KeyboardButton(text="CNY"),
        KeyboardButton(text="Отмена")
    )
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )


# Обработчики команд
@dp.message(Command('start'))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    conn = None
    try:
        conn = await create_db_connection()
        user_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE chat_id = $1",
            message.from_user.id
        )

        if not user_exists:
            await message.answer(
                "👋 Добро пожаловать в Finance Bot!\n\n"
                "Пожалуйста, зарегистрируйтесь с помощью команды /register"
            )
        else:
            await message.answer(
                "🔄 Бот уже запущен\n"
                "Используйте кнопки ниже для работы",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке /start: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()


@dp.message(Command('register'))
async def cmd_register(message: Message, state: FSMContext):
    """Обработчик команды /register"""
    conn = None
    try:
        conn = await create_db_connection()
        user_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE chat_id = $1",
            message.from_user.id
        )

        if user_exists:
            await message.answer("ℹ️ Вы уже зарегистрированы!")
            return

        await message.answer(
            "📝 Введите ваше имя для регистрации:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(RegistrationState.waiting_for_name)
    except Exception as e:
        logger.error(f"Ошибка при регистрации: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()


@dp.message(RegistrationState.waiting_for_name)
async def process_registration_name(message: Message, state: FSMContext):
    """Обработка имени при регистрации"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Регистрация отменена", reply_markup=types.ReplyKeyboardRemove())
        return

    conn = None
    try:
        conn = await create_db_connection()
        await conn.execute(
            "INSERT INTO users (chat_id, name) VALUES ($1, $2)",
            message.from_user.id, message.text.strip()
        )
        await message.answer(
            f"✅ Регистрация успешна, {message.text.strip()}!\n"
            "Теперь вы можете начать вести учет финансов.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()
        await state.clear()


# Обработчик команды /update_operation
@dp.message(Command('update_operation'))
async def cmd_update_operation(message: Message, state: FSMContext):
    """Обработчик команды /update_operation с выводом списка операций"""
    conn = None
    try:
        conn = await create_db_connection()
        user_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE chat_id = $1",
            message.from_user.id
        )

        if not user_exists:
            await message.answer("ℹ️ Пожалуйста, сначала зарегистрируйтесь с помощью /register")
            return

        # Получаем последние 10 операций пользователя
        operations = await conn.fetch(
            "SELECT id, type_operation, sum, date FROM operations "
            "WHERE chat_id = $1 ORDER BY date DESC, id DESC LIMIT 10",
            message.from_user.id
        )

        if not operations:
            await message.answer("ℹ️ У вас пока нет операций для изменения")
            return

        # Формируем сообщение со списком операций
        operations_list = ["📋 Ваши последние операции (ID - Дата - Сумма - Тип):"]
        for op in operations:
            op_type = "Доход" if op['type_operation'] == 'income' else "Расход"
            operations_list.append(
                f"🆔 {op['id']} - {op['date'].strftime('%d.%m.%Y')} - {op['sum']:.2f} RUB - {op_type}"
            )

        operations_list.append("\nВведите ID операции, которую хотите изменить:")

        await message.answer(
            "\n".join(operations_list),
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UpdateOperationState.waiting_for_operation_id)
    except Exception as e:
        logger.error(f"Ошибка при начале обновления операции: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()


# Обработка ID операции
@dp.message(UpdateOperationState.waiting_for_operation_id)
async def process_operation_id(message: Message, state: FSMContext):
    """Обработка ID операции для обновления"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Изменение операции отменено", reply_markup=get_main_keyboard())
        return

    conn = None
    try:
        operation_id = int(message.text)
        conn = await create_db_connection()

        # Проверяем, что операция существует и принадлежит пользователю
        operation_exists = await conn.fetchval(
            "SELECT 1 FROM operations WHERE id = $1 AND chat_id = $2",
            operation_id, message.from_user.id
        )

        if not operation_exists:
            await message.answer("⚠️ Операция с таким ID не найдена или не принадлежит вам. Попробуйте еще раз.")
            return

        await state.update_data(operation_id=operation_id)
        await message.answer(
            "Введите новую сумму для операции:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UpdateOperationState.waiting_for_new_amount)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный ID операции (целое число)")
    except Exception as e:
        logger.error(f"Ошибка при проверке операции: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()


# Обработка новой суммы операции
@dp.message(UpdateOperationState.waiting_for_new_amount)
async def process_new_amount(message: Message, state: FSMContext):
    """Обработка новой суммы операции"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Изменение операции отменено", reply_markup=get_main_keyboard())
        return

    try:
        new_amount = float(message.text.replace(',', '.'))
        if new_amount <= 0:
            await message.answer("⚠️ Сумма должна быть больше нуля. Попробуйте еще раз.")
            return

        operation_data = await state.get_data()
        conn = None

        try:
            conn = await create_db_connection()
            await conn.execute(
                "UPDATE operations SET sum = $1 WHERE id = $2 AND chat_id = $3",
                new_amount, operation_data['operation_id'], message.from_user.id
            )

            # Получаем обновленную операцию для отображения пользователю
            updated_operation = await conn.fetchrow(
                "SELECT type_operation, sum, date FROM operations WHERE id = $1",
                operation_data['operation_id']
            )

            operation_type = "доход" if updated_operation['type_operation'] == 'income' else "расход"
            await message.answer(
                f"✅ Операция успешно обновлена!\n\n"
                f"Тип: {operation_type}\n"
                f"Новая сумма: {updated_operation['sum']:.2f} RUB\n"
                f"Дата: {updated_operation['date'].strftime('%d.%m.%Y')}",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении операции: {str(e)}")
            await message.answer("⚠️ Произошла ошибка при обновлении операции. Пожалуйста, попробуйте позже.")
        finally:
            if conn:
                await conn.close()
            await state.clear()
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректную сумму (например: 1500.50)")


@dp.message(lambda message: message.text == "➕ Добавить операцию")
async def add_operation_start(message: Message, state: FSMContext):
    """Начало добавления операции"""
    conn = None
    try:
        conn = await create_db_connection()
        user_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE chat_id = $1",
            message.from_user.id
        )

        if not user_exists:
            await message.answer("ℹ️ Пожалуйста, сначала зарегистрируйтесь с помощью /register")
            return

        await message.answer(
            "Выберите тип операции:",
            reply_markup=get_operation_type_keyboard()
        )
        await state.set_state(AddOperationState.waiting_for_type)
    except Exception as e:
        logger.error(f"Ошибка при начале добавления операции: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()


@dp.message(AddOperationState.waiting_for_type)
async def process_operation_type(message: Message, state: FSMContext):
    """Обработка типа операции"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Добавление операции отменено", reply_markup=get_main_keyboard())
        return

    if message.text not in ["Доход", "Расход"]:
        await message.answer("Пожалуйста, выберите тип операции используя кнопки")
        return

    await state.update_data(operation_type='income' if message.text == "Доход" else 'expense')
    await message.answer(
        "💵 Введите сумму операции:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddOperationState.waiting_for_amount)


@dp.message(AddOperationState.waiting_for_amount)
async def process_operation_amount(message: Message, state: FSMContext):
    """Обработка суммы операции"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Добавление операции отменено", reply_markup=get_main_keyboard())
        return

    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("⚠️ Сумма должна быть больше нуля. Попробуйте еще раз.")
            return

        await state.update_data(amount=amount)
        await message.answer(
            "📅 Введите дату операции в формате ДД.ММ.ГГГГ или нажмите 'Сегодня'",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Сегодня")],
                    [KeyboardButton(text="Отмена")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(AddOperationState.waiting_for_date)
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректную сумму (например: 1500.50)")


@dp.message(AddOperationState.waiting_for_date)
async def process_operation_date(message: Message, state: FSMContext):
    """Обработка даты операции"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Добавление операции отменено", reply_markup=get_main_keyboard())
        return

    operation_data = await state.get_data()
    conn = None

    try:
        if message.text == "Сегодня":
            operation_date = datetime.now().date()  # Теперь будет работать правильно
        else:
            operation_date = datetime.strptime(message.text, "%d.%m.%Y").date()

        conn = await create_db_connection()
        await conn.execute(
            "INSERT INTO operations (chat_id, type_operation, sum, date) VALUES ($1, $2, $3, $4)",
            message.from_user.id,
            operation_data['operation_type'],
            operation_data['amount'],
            operation_date
        )

        operation_type = "доход" if operation_data['operation_type'] == 'income' else "расход"
        await message.answer(
            f"✅ Операция успешно добавлена!\n\n"
            f"Тип: {operation_type}\n"
            f"Сумма: {operation_data['amount']:.2f} RUB\n"
            f"Дата: {operation_date.strftime('%d.%m.%Y')}",
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        await message.answer("⚠️ Неверный формат даты. Используйте ДД.ММ.ГГГГ или кнопку 'Сегодня'")
        return
    except Exception as e:
        logger.error(f"Ошибка при сохранении операции: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при сохранении операции. Пожалуйста, попробуйте позже.")
    finally:
        if conn:
            await conn.close()
        await state.clear()


@dp.message(lambda message: message.text == "📊 Отчеты")
async def reports_menu(message: Message, state: FSMContext):
    """Меню отчетов"""
    await message.answer(
        "Выберите валюту для отчета:",
        reply_markup=get_currency_keyboard()
    )
    await state.set_state(ReportState.waiting_for_currency)


@dp.message(ReportState.waiting_for_currency)
async def process_report_currency(message: Message, state: FSMContext):
    """Обработка выбора валюты для отчета"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Создание отчета отменено", reply_markup=get_main_keyboard())
        return

    if message.text not in ["RUB", "USD", "EUR", "CNY"]:
        await message.answer("Пожалуйста, выберите валюту из предложенных вариантов")
        return

    await state.update_data(currency=message.text)
    await message.answer(
        "Выберите период для отчета:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="За сегодня"), KeyboardButton(text="За неделю")],
                [KeyboardButton(text="За месяц"), KeyboardButton(text="За все время")],
                [KeyboardButton(text="Отмена")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(ReportState.waiting_for_period)


@dp.message(ReportState.waiting_for_period)
async def process_report_period(message: Message, state: FSMContext):
    """Генерация и отправка отчета"""
    if message.text == "Отмена":
        await state.clear()
        await message.answer("❌ Создание отчета отменено", reply_markup=get_main_keyboard())
        return

    period_mapping = {
        "За сегодня": timedelta(days=1),
        "За неделю": timedelta(weeks=1),
        "За месяц": timedelta(days=30),
        "За все время": None
    }

    if message.text not in period_mapping:
        await message.answer("Пожалуйста, выберите период из предложенных вариантов")
        return

    report_data = await state.get_data()
    currency = report_data['currency']
    conn = None

    try:
        conn = await create_db_connection()

        # Получение курса валюты
        rate = 1.0
        if currency != 'RUB':
            rate = await get_exchange_rate(currency)
            if rate is None:
                await message.answer(
                    "⚠️ Не удалось получить курс валюты. Отчет будет в RUB.",
                    reply_markup=get_main_keyboard()
                )
                currency = 'RUB'
                rate = 1.0

        # Формирование SQL запроса в зависимости от периода
        if message.text == "За все время":
            operations = await conn.fetch(
                "SELECT type_operation, sum, date FROM operations "
                "WHERE chat_id = $1 ORDER BY date DESC",
                message.from_user.id
            )
        else:
            operations = await conn.fetch(
                "SELECT type_operation, sum, date FROM operations "
                "WHERE chat_id = $1 AND date >= (NOW() - $2::interval) "
                "ORDER BY date DESC",
                message.from_user.id,
                period_mapping[message.text]
            )

        if not operations:
            await message.answer(
                f"ℹ️ Нет операций за выбранный период ({message.text.lower()})",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        # Формирование отчёта
        report_lines = [f"📊 Отчет за {message.text.lower()} ({currency}):\n"]

        for op in operations:
            amount = float(op['sum']) / rate
            prefix = "⬆️" if op['type_operation'] == 'income' else "⬇️"

            report_lines.append(
                f"{prefix} {op['date'].strftime('%d.%m.%Y')} - {amount:.2f} {currency}"
            )

        await message.answer("\n".join(report_lines), reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при формировании отчета: {str(e)}")
        await message.answer(
            "⚠️ Произошла ошибка при формировании отчета. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
    finally:
        if conn:
            await conn.close()
        await state.clear()


@dp.message(lambda message: message.text == "ℹ️ Помощь")
async def show_help(message: Message):
    """Показывает справку по боту"""
    help_text = (
        "📚 <b>Помощь по Finance Bot</b>\n\n"
        "Основные команды:\n"
        "/start - Запустить бота\n"
        "/register - Регистрация\n"
        "/update_operation - Изменить операцию\n\n"
        "Основные функции:\n"
        "➕ Добавить операцию - Внести новую операцию (доход/расход)\n"
        "📊 Отчеты - Просмотр статистики за период\n\n"
        "Для добавления операции укажите:\n"
        "1. Тип (доход/расход)\n"
        "2. Сумму\n"
        "3. Дату\n\n"
        "Отчеты можно получить в разных валютах."
    )
    await message.answer(help_text, parse_mode='HTML')


@dp.message()
async def handle_unknown_message(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.answer(
        "Я не понимаю эту команду. Пожалуйста, используйте кнопки меню или команду /help",
        reply_markup=get_main_keyboard()
    )


async def main():
    """Основная функция запуска бота"""
    await init_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())