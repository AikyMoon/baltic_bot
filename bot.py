from handlers import region, routes


import os
import asyncio
import json
import logging
import urllib.parse
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ЗАГРУЗКА МАРШРУТОВ ИЗ JSON ФАЙЛА ---
JSON_FILE_PATH = "data/tours.json"
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
    await command_start_handler(query.message) # Переиспользуем команду /start
    logger.info(f"Возврат в главное меню для {query.from_user.id}")


# --- КОНЕЦ ОБРАБОТЧИКОВ ---


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Главное меню"),
        # BotCommand(command="routes", description="Показать все маршруты") # Обновил описание
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды установлены")


dp.include_router(region.router)
dp.include_router(routes.router)


async def main():
    logger.info("Бот запускается...")
    await set_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())