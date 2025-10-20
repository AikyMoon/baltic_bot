import os
import json
import logging
import urllib.parse
from typing import Optional, List, Dict, Any, Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

router = Router()
logger = logging.getLogger("TourBot")

# --- Константы и загрузка данных ---
ROUTES_FILE = "data/tours.json"
IMAGE_DIR = "tourism_bot/images"
AUDIO_DIR = "tourism_bot/audio" # Новая папка для аудиофайлов
PLACEHOLDER_IMAGE = os.path.join(IMAGE_DIR, "placeholder.jpg")

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True) # Создаем папку для аудио


# Загрузка данных маршрутов
ROUTES_DATA: List[Dict[str, Any]] = []
try:
    with open(ROUTES_FILE, "r", encoding="utf-8") as f:
        loaded_data = json.load(f)
        if "routes" in loaded_data:
            ROUTES_DATA = loaded_data["routes"]
        else:
            logger.error(f"Файл данных {ROUTES_FILE} не содержит ключа 'routes'.")
except FileNotFoundError:
    logger.error(f"Файл данных не найден: {ROUTES_FILE}. Проверьте путь.")
except json.JSONDecodeError as e:
    logger.error(f"Ошибка декодирования JSON в файле {ROUTES_FILE}: {e}")


# --- Вспомогательные функции ---

def _get_route_data(route_id: str) -> Optional[Dict[str, Any]]:
    """Возвращает данные маршрута по ID."""
    return next((r for r in ROUTES_DATA if r["id"] == route_id), None)


def get_image_source(entity_id: str, image_obj: Optional[Dict[str, str]]) -> Optional[str]:
    """
    Определяет путь к изображению: сначала локальный, потом URL, затем общая заглушка.
    Принимает объект вида {"local": "image.jpg", "url": "http://..."}.
    Использует entity_id (region_id или route_id) для формирования пути к локальным изображениям.
    """
    if image_obj is None:
        return PLACEHOLDER_IMAGE if os.path.exists(PLACEHOLDER_IMAGE) else None

    local_filename = image_obj.get("local")
    if local_filename:
        # Путь к локальному изображению внутри папки региона/маршрута
        full_local_path = os.path.join(IMAGE_DIR, entity_id, local_filename)
        
        if os.path.exists(full_local_path):
            return full_local_path
        else:
            logger.debug(f"Локальный файл не найден: {full_local_path}")

    url = image_obj.get("url")
    # if isinstance(url, str) and url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
    if isinstance(url, str):

        return url

    return PLACEHOLDER_IMAGE if os.path.exists(PLACEHOLDER_IMAGE) else None


def get_audio_source(entity_id: str, audio_obj: Optional[Dict[str, str]]) -> Optional[str]:
    """
    Определяет путь к аудиофайлу: сначала локальный, потом URL.
    Принимает объект вида {"local": "audio.mp3", "url": "http://..."}.
    Использует entity_id (route_id) для формирования пути к локальным аудио.
    """
    if audio_obj is None:
        return None

    local_filename = audio_obj.get("local")
    if local_filename:
        # Путь к локальному аудиофайлу внутри папки маршрута
        full_local_path = os.path.join(AUDIO_DIR, entity_id, local_filename)
        
        if os.path.exists(full_local_path):
            return full_local_path
        else:
            logger.debug(f"Локальный аудиофайл не найден: {full_local_path}")

    url = audio_obj.get("url")
    # if isinstance(url, str) and url.lower().endswith((".mp3", ".ogg", ".wav", ".m4a")):
    if isinstance(url, str):

        return url

    return None


def split_long(text: str, limit: int = 4000) -> List[str]:
    """Разбивает длинный текст на части."""
    if not text:
        return []
    return [text[i:i + limit] for i in range(0, len(text), limit)]


async def send_and_replace(query_or_message: Union[CallbackQuery, Message], text: str, image_path: Optional[str], markup):
    """
    Отправляет новое сообщение (photo или text) и, если это CallbackQuery, удаляет старое.
    Поддерживает длинные подписи для фото и текста.
    """
    is_callback = isinstance(query_or_message, CallbackQuery)
    chat_id = query_or_message.message.chat.id if is_callback else query_or_message.chat.id
    
    caption_limit = 1024 if image_path else 4096 # Лимит для подписи фото / текста

    main_caption = text[:caption_limit]
    remaining_text = text[caption_limit:] if len(text) > caption_limit else ""

    print(image_path)

    try:
        if image_path:
            if os.path.exists(image_path) and os.path.isfile(image_path):
                await query_or_message.bot.send_photo(chat_id=chat_id, photo=FSInputFile(image_path),
                                           caption=main_caption, parse_mode="Markdown", reply_markup=markup)
            else:
                await query_or_message.bot.send_photo(chat_id=chat_id, photo=image_path,
                                           caption=main_caption, parse_mode="Markdown", reply_markup=markup)
            
            if remaining_text:
                for part in split_long(remaining_text, limit=4096):
                    await query_or_message.bot.send_message(chat_id=chat_id, text=part, parse_mode="Markdown")
        else:
            await query_or_message.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.warning(f"Ошибка при отправке нового сообщения: {e}")
        # Если что-то пошло не так с фото, попробуем отправить только текст без фото
        await query_or_message.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=markup)

    if is_callback:
        try:
            await query_or_message.message.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить старое сообщение {query_or_message.message.message_id}: {e}")
        try:
            await query_or_message.answer()
        except Exception: 
            pass


# --- ОБРАБОТЧИКИ (ОБЩИЕ И ДЛЯ РЕГИОНОВ - ВАШ СУЩЕСТВУЮЩИЙ КОД) ---

# Предполагаем, что у вас есть где-то обработчик для "go_to_start"
# @router.callback_query(F.data == "go_to_start")
# async def go_to_start(query: CallbackQuery):
#     await query.answer()
#     # Здесь должна быть логика для показа главного меню
#     await query.message.answer("Добро пожаловать в главное меню!") 


# --- НОВЫЕ И ИСПРАВЛЕННЫЕ ОБРАБОТЧИКИ ДЛЯ МАРШРУТОВ ---

@router.message(Command("routes"))
@router.callback_query(F.data == "show_routes")
async def show_routes_menu(query_or_message: Union[Message, CallbackQuery]):
    if isinstance(query_or_message, CallbackQuery):
        message = query_or_message.message
        await query_or_message.answer()
    else:
        message = query_or_message

    if not ROUTES_DATA:
        await message.answer("Извините, маршруты в данный момент недоступны. Попробуйте позже.")
        logger.warning("ROUTES_DATA пуст.")
        return

    kb = InlineKeyboardBuilder()
    for route in ROUTES_DATA:
        kb.add(InlineKeyboardButton(text=route["name"], callback_data=f"route_{route['id']}_intro"))
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_start"))
    await send_and_replace(query_or_message, """"Секреты Балтики" ждут! 🗺️

Прежде чем отправиться в путь, давайте выберем ваш идеальный маршрут! ✨ Куда зовёт вас дух приключений сегодня?

📍 По центру Калининграда: Откройте для себя сердце города — его историю, архитектуру и знаковые места.
📍 Вдоль берегов Преголи: Прогуляйтесь по набережным, где каждый камень хранит свои тайны.
📍 К Балтийскому морю и его курортам: Почувствуйте свежий бриз, бескрайние дюны и очарование приморских городов.
Выберите свой путь, и Балти покажет вам самые удивительные места! 👇""", None, kb.as_markup())
    logger.info(f"Показаны маршруты для {message.from_user.id}")


@router.callback_query(F.data.startswith("route_") & F.data.contains("_intro"))
async def route_intro(query: CallbackQuery):
    await query.answer()

    try:
        _, route_id, _ = query.data.split("_", 2)
        route = _get_route_data(route_id)

        if not route:
            await query.message.answer("Извините, выбранный маршрут не найден.")
            logger.warning(f"Маршрут с ID {route_id} не найден.")
            return

        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➡️ Начать маршрут", callback_data=f"route_{route_id}_point_0_0"))
        
        kb.row(
            InlineKeyboardButton(text="⬅️ К списку маршрутов", callback_data="show_routes"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_start")
        )
        kb.adjust(1)

        description_text = f"🗺 *{route['name']}*\n\n{route['description']}"
        
        map_link_text = ""
        points_on_map = [p for p in route.get('points', []) if p.get('latitude') is not None and p.get('longitude') is not None]

        if route.get("map_url"):
            map_link_text = f"\n\n[🗺 Открыть весь маршрут на карте]({route['map_url']})"
        elif len(points_on_map) >= 2:
            origin_lat, origin_lon = points_on_map[0]["latitude"], points_on_map[0]["longitude"]
            destination_lat, destination_lon = points_on_map[-1]["latitude"], points_on_map[-1]["longitude"]

            waypoints = []
            for i in range(1, len(points_on_map) - 1): 
                waypoints.append(f"{points_on_map[i]['latitude']},{points_on_map[i]['longitude']}")
            
            waypoints_str = urllib.parse.quote("|".join(waypoints)) if waypoints else ""

            google_maps_route_url = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={origin_lat},{origin_lon}"
                f"&destination={destination_lat},{destination_lon}"
            )
            if waypoints_str:
                google_maps_route_url += f"&waypoints={waypoints_str}"
            
            map_link_text = f"\n\n[🗺 Открыть полный маршрут на Google Картах]({google_maps_route_url})"
        elif len(points_on_map) == 1:
            map_link_text = f"\n\n[🗺 Показать стартовую точку на Google Картах](https://www.google.com/maps/search/?api=1&query={points_on_map[0]['latitude']},{points_on_map[0]['longitude']})"
        
        description_text += map_link_text

        image_path = get_image_source(route_id, route.get("image"))

        await send_and_replace(query, description_text, image_path, kb.as_markup())
        logger.info(f"Показано описание маршрута {route_id} для {query.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка в route_intro для {query.from_user.id}: {e}", exc_info=True)
        await query.message.answer("Произошла непредвиденная ошибка. Пожалуйста, попробуйте еще раз или обратитесь за помощью.")


@router.callback_query(F.data.startswith("route_") & F.data.contains("_point_"))
async def route_point_detail(query: CallbackQuery):
    try:
        _, route_id, _, idx_str, show_full_str = query.data.split("_", 4)
        idx = int(idx_str)
        show_full = bool(int(show_full_str))
    except Exception:
        await query.answer("Неправильные данные запроса", show_alert=True)
        return

    route = _get_route_data(route_id)
    if not route:
        await query.answer("Маршрут не найден", show_alert=True)
        return

    points = route.get("points", [])
    if idx < 0 or idx >= len(points):
        text = "Это конец маршрута! Надеемся, вам понравилось ваше путешествие!"
        kb_end = InlineKeyboardBuilder()
        kb_end.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_start"))
        kb_end.row(InlineKeyboardButton(text="⬅️ Выбрать другой маршрут", callback_data="show_routes"))
        if route.get("map_url"):
            kb_end.row(InlineKeyboardButton(text="🗺 Весь маршрут на карте", url=route['map_url']))
        await send_and_replace(query, text, None, kb_end.as_markup())
        logger.info(f"Конец маршрута {route_id} для {query.from_user.id}")
        return

    pt = points[idx]
    name = pt.get("name", "Точка маршрута")
    
    description = pt.get("full_description" if show_full else "short_description", "Описание отсутствует.")
    if not description and not show_full:
        description = pt.get("full_description", "Описание отсутствует.")

    fact = pt.get("fact", "")
    address = pt.get("address", "")
    hours = pt.get("hours", "")
    price = pt.get("price", "")

    text_parts = [f"📍 *{name}*\n\n{description}"]
    
    if fact:
        text_parts.append(f"\n_💡 Интересный факт: {fact}_")
    if address:
        text_parts.append(f"📍 *Адрес:* {address}")
    if hours:
        text_parts.append(f"⏱ *Часы работы:* {hours}")
    if price:
        text_parts.append(f"💵 *Стоимость:* {price}")

    text = "\n".join(text_parts)

    image_path = get_image_source(route_id, pt.get("image"))

    kb = InlineKeyboardBuilder()

    if pt.get("full_description") and pt.get("short_description") and pt["full_description"] != pt["short_description"]:
        if not show_full:
            kb.add(InlineKeyboardButton(text="📖 Подробнее", callback_data=f"route_{route_id}_point_{idx}_1"))
        else:
            kb.add(InlineKeyboardButton(text="⬅️ Свернуть", callback_data=f"route_{route_id}_point_{idx}_0"))
        kb.adjust(1)

    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая точка", callback_data=f"route_{route_id}_point_{idx-1}_0"))
    if idx + 1 < len(points):
        nav_buttons.append(InlineKeyboardButton(text="Следующая точка ➡️", callback_data=f"route_{route_id}_point_{idx+1}_0"))
    if nav_buttons:
        kb.row(*nav_buttons)

    action_buttons = []
    # --- ДОБАВЛЕНИЕ КНОПКИ АУДИОГИДА ---
    if pt.get("audio"): # Проверяем наличие поля "audio"
        action_buttons.append(InlineKeyboardButton(text="🎵 Аудиогид", callback_data=f"audio_{route_id}_{idx}"))
    # --- КОНЕЦ ДОБАВЛЕНИЯ КНОПКИ АУДИОГИДА ---

    if pt.get("latitude") is not None and pt.get("longitude") is not None:
        action_buttons.append(InlineKeyboardButton(text="🗺 На карте", url=f"https://yandex.ru/maps/?text={pt['latitude']},{pt['longitude']}"))
    elif pt.get("address"):
        action_buttons.append(InlineKeyboardButton(text="🗺 На карте", url=f"https://yandex.ru/maps/?text={urllib.parse.quote(pt['address'])}"))
    if action_buttons:
        kb.row(*action_buttons)
    
    kb.row(InlineKeyboardButton(text="⬅️ В меню маршрута", callback_data=f"route_{route_id}_intro"))
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_start"))

    await send_and_replace(query, text, image_path, kb.as_markup())
    logger.info(f"Показана точка {idx} маршрута {route_id} для {query.from_user.id}")


# --- НОВЫЙ ОБРАБОТЧИК ДЛЯ АУДИОГИДА ---
@router.callback_query(F.data.startswith("audio_"))
async def send_audio_guide(query: CallbackQuery):
    await query.answer("Загружаю аудиогид...", show_alert=False)
    
    try:
        _, route_id, idx_str = query.data.split("_", 2)
        idx = int(idx_str)

        route = _get_route_data(route_id)
        if not route:
            await query.message.answer("Маршрут не найден.", parse_mode="Markdown")
            return

        points = route.get("points", [])
        if idx < 0 or idx >= len(points):
            await query.message.answer("Точка маршрута не найдена.", parse_mode="Markdown")
            return

        pt = points[idx]
        audio_obj = pt.get("audio")
        
        audio_source = get_audio_source(route_id, audio_obj)

        if audio_source:
            try:
                caption = f"🎵 *Аудиогид к точке: {pt.get('name', 'Без названия')}*"
                if os.path.exists(audio_source) and os.path.isfile(audio_source):
                    await query.bot.send_audio(chat_id=query.message.chat.id, audio=FSInputFile(audio_source), caption=caption, parse_mode="Markdown")
                    logger.info(f"Отправлен локальный аудиофайл для точки {idx} маршрута {route_id} пользователю {query.from_user.id}")
                else:
                    await query.bot.send_audio(chat_id=query.message.chat.id, audio=audio_source, caption=caption, parse_mode="Markdown")
                    logger.info(f"Отправлен аудиофайл по URL для точки {idx} маршрута {route_id} пользователю {query.from_user.id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке аудиофайла для точки {idx} маршрута {route_id}: {e}", exc_info=True)
                await query.message.answer("Произошла ошибка при загрузке аудиогида.", parse_mode="Markdown")
        else:
            await query.message.answer("К сожалению, для этой точки аудиогид пока недоступен.", parse_mode="Markdown")
            logger.info(f"Аудиогид не найден для точки {idx} маршрута {route_id}")

    except Exception as e:
        logger.error(f"Ошибка в send_audio_guide для {query.from_user.id}: {e}", exc_info=True)
        await query.message.answer("Произошла непредвиденная ошибка при обработке аудиогида.")