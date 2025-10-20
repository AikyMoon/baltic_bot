# main.py
from handlers import region, routes

import os
import asyncio
import json
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

# --- ИЗМЕНЕНИЯ ДЛЯ AIOGRAM 3.x WEBHOOK (БЕЗ Simple) ---
from aiohttp import web
# Проверяем наличие Simple и импортируем, если есть, иначе используем альтернативу
try:
    from aiogram.webhook.aiohttp_server import Simple, setup_application
    USE_SIMPLE_HANDLER = True
except ImportError:
    from aiogram.webhook.aiohttp_server import setup_application
    USE_SIMPLE_HANDLER = False
    logging.warning("Simple handler not found in aiogram.webhook.aiohttp_server. Using direct setup_application.")
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- КОНФИГУРАЦИЯ WEBHOOK ---
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST')
if not WEBHOOK_HOST:
    pa_username = os.getenv("PA_USERNAME")
    WEBHOOK_HOST = f'https://{pa_username}.pythonanywhere.com' if pa_username else "http://localhost"

WEBHOOK_PATH = f'/webhook/{TOKEN}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'

WEBAPP_HOST = '127.0.0.1'
WEBAPP_PORT = int(os.getenv('PORT', 5000))
# --- КОНЕЦ КОНФИГУРАЦИИ WEBHOOK ---


# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА МАРШРУТОВ ИЗ JSON ФАЙЛА ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(BASE_DIR, "data", "tours.json")
ROUTES = []
try:
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        ROUTES = json.load(f)["routes"]
    logger.info("Маршруты успешно загружены.")
except FileNotFoundError:
    logger.error(f"Файл {JSON_FILE_PATH} не найден. Убедитесь, что он расположен по верному пути.")
except json.JSONDecodeError:
    logger.error(f"Ошибка при парсинге {JSON_FILE_PATH}. Проверьте корректность JSON-формата.")
# --- КОНЕЦ ЗАГРУЗКИ МАРШРУТОВ ---


# --- ОБРАБОТЧИКИ КОМАНД И CALLBACKS ---

@dp.message(Command("start"))
async def command_start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🗺 Посмотреть маршруты", callback_data="show_routes"))
    kb.row(InlineKeyboardButton(text="ℹ️ Узнать о регионе", callback_data="region_kaliningrad"))
    
    await message.answer(
        "Привет! Я — Балти, ваш персональный гид и хранитель всех тайн Калининградской области. Готовы раскрыть «Секреты Балтики» вместе? От древних замков до янтарных берегов, от истории Кёнигсберга до современного Калининграда — я покажу вам самое интересное!\n Что из этого многообразия вас интересует в первую очередь?",
        reply_markup=kb.as_markup()
    )
    logger.info(f"Получена команда /start от {message.from_user.id}")


@dp.callback_query(F.data == "go_to_start")
async def go_to_start_callback(query: CallbackQuery):
    await query.answer()
    await command_start_handler(query.message)
    logger.info(f"Возврат в главное меню для {query.from_user.id}")

# --- КОНЕЦ ОБРАБОТЧИКОВ ---


async def set_commands(bot_obj: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню"),
    ]
    await bot_obj.set_my_commands(commands)
    logger.info("Команды установлены")


# --- Функции on_startup и on_shutdown для WEBHOOK ---
async def on_startup_webhook(bot_obj: Bot):
    logger.info("Запуск бота через webhook...")
    await set_commands(bot_obj)
    await bot_obj.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"Webhook установлен на: {WEBHOOK_URL}")

async def on_shutdown_webhook(bot_obj: Bot):
    logger.info("Выключение бота через webhook...")
    await bot_obj.delete_webhook()
    logger.info("Webhook удален.")
# --- КОНЕЦ Функций для WEBHOOK ---


dp.include_router(region.router)
dp.include_router(routes.router)


# --- Функция для запуска webhook-сервера Aiogram ---
async def start_webhook_server():
    app = web.Application()

    # Измененный участок: используем setup_application напрямую
    if USE_SIMPLE_HANDLER:
        webhook_requests_handler = Simple(dispatcher=dp, bot=bot, path=WEBHOOK_PATH)
        setup_application(app, webhook_requests_handler)
    else:
        # Прямая настройка без Simple
        # Aiogram 3.x ожидает, что setup_application будет настроен именно так
        setup_application(app, dp, bot=bot, path=WEBHOOK_PATH) 

    await on_startup_webhook(bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logger.info(f"Aiohttp web server started on {WEBAPP_HOST}:{WEBAPP_PORT}")

    while True:
        await asyncio.sleep(3600)

# --- Функция для запуска в режиме polling ---
async def start_polling_server():
    logger.info("Запуск бота в режиме polling...")
    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    run_as_webhook = os.getenv("RUN_AS_WEBHOOK", "False").lower() == "true"
    
    if run_as_webhook:
        logger.info("Запуск бота в режиме WEBHOOK.")
        asyncio.run(start_webhook_server())
    else:
        logger.info("Запуск бота в режиме POLLING.")
        asyncio.run(start_polling_server())