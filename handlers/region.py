import os
import json
import logging
from typing import Optional, List, Dict, Any

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

router = Router()
logger = logging.getLogger("TourBot")

# --- Константы и загрузка данных ---
DATA_FILE = "tourism_bot/data/regions2.json"  # Убедитесь, что путь к вашему JSON верен
IMAGE_DIR = "tourism_bot/images"
PLACEHOLDER_IMAGE = os.path.join(IMAGE_DIR, "placeholder.jpg")  # Общая заглушка, если нет других

# Убедитесь, что IMAGE_DIR существует
os.makedirs(IMAGE_DIR, exist_ok=True)

# Загрузка данных
REGIONS_DATA: List[Dict[str, Any]] = []
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        loaded_data = json.load(f)
        if "regions" in loaded_data:
            REGIONS_DATA = loaded_data["regions"]
        else:
            logger.error(f"Файл данных {DATA_FILE} не содержит ключа 'regions'.")
except FileNotFoundError:
    logger.error(f"Файл данных не найден: {DATA_FILE}. Проверьте путь.")
except json.JSONDecodeError as e:
    logger.error(f"Ошибка декодирования JSON в файле {DATA_FILE}: {e}")


# --- Вспомогательные функции ---

def _get_region_data(region_id: str) -> Optional[Dict[str, Any]]:
    """Возвращает данные региона по ID."""
    return next((r for r in REGIONS_DATA if r["id"] == region_id), None)

def get_image_source(region_id: str, image_obj: Optional[Dict[str, str]]) -> Optional[str]:
    """
    Определяет путь к изображению: сначала локальный, потом URL, затем общая заглушка.
    Принимает объект вида {"local": "image.jpg", "url": "http://..."}.
    """
    if image_obj is None:
        return PLACEHOLDER_IMAGE if os.path.exists(PLACEHOLDER_IMAGE) else None

    local_filename = image_obj.get("local")
    if local_filename:
        # Путь к локальному изображению внутри папки региона
        full_local_path = os.path.join(IMAGE_DIR, region_id, local_filename)
        
        if os.path.exists(full_local_path):
            return full_local_path
        else:
            logger.debug(f"Локальный файл не найден: {full_local_path}")

    url = image_obj.get("url")
    if isinstance(url, str):
        return url

    return PLACEHOLDER_IMAGE if os.path.exists(PLACEHOLDER_IMAGE) else None


def split_long(text: str, limit: int = 4000) -> List[str]:
    """Разбивает длинный текст на части."""
    return [text[i:i + limit] for i in range(0, len(text), limit)]


async def send_and_replace(query: CallbackQuery, text: str, image_path: Optional[str], markup):
    """
    Отправляет новое сообщение (photo или text) и удаляет старое.
    Отправляет новое первым, чтобы callback не терялся у Telegram.
    Поддерживает длинные подписи для фото и текста.
    """
    chat_id = query.message.chat.id
    caption_limit = 1024 if image_path else 4096 # Лимит для подписи фото / текста

    main_caption = text[:caption_limit]
    remaining_text = text[caption_limit:] if len(text) > caption_limit else ""

    try:
        if image_path:
            # Проверяем, является ли путь локальным файлом или URL
            if os.path.exists(image_path) and os.path.isfile(image_path):
                # Отправляем локальный файл
                await query.bot.send_photo(chat_id=chat_id, photo=FSInputFile(image_path),
                                           caption=main_caption, parse_mode="Markdown", reply_markup=markup)
            else:
                # Отправляем по URL или если image_path оказался URL
                await query.bot.send_photo(chat_id=chat_id, photo=image_path,
                                           caption=main_caption, parse_mode="Markdown", reply_markup=markup)
            
            # Отправляем оставшийся текст как отдельные сообщения
            if remaining_text:
                for part in split_long(remaining_text, limit=4096):
                    await query.bot.send_message(chat_id=chat_id, text=part, parse_mode="Markdown")
        else:
            # Если нет изображения, отправляем только текст
            await query.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.warning(f"Ошибка при отправке нового сообщения: {e}")
        # Если что-то пошло не так с фото, попробуем отправить только текст без фото
        await query.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=markup)

    # Пытаемся удалить старое сообщение
    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить старое сообщение {query.message.message_id}: {e}")

    try:
        await query.answer()
    except Exception: # answer() может бросить ошибку, если уже ответили
        pass


# --- Обработчики ---

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    kb = InlineKeyboardBuilder()
    for r in REGIONS_DATA:
        kb.add(InlineKeyboardButton(text=r["display_name"], callback_data=f"region_{r['id']}"))
    kb.adjust(1)
    await message.answer("🌍 Выберите регион:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("region_"))
async def region_menu(query: CallbackQuery):
    region_id = query.data.split("region_")[1]
    region = _get_region_data(region_id)
    if not region:
        await query.answer("Регион не найден", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    sections = [
        ("1️⃣ Общие сведения", "geography"),
        ("2️⃣ Природные ресурсы", "resources"),
        ("3️⃣ История", "history"),
        ("4️⃣ Экономика", "economy"),
        ("5️⃣ Культура", "culture"),
        ("6️⃣ Достопримечательности", "sights")
    ]
    for label, key in sections:
        kb.add(InlineKeyboardButton(text=label, callback_data=f"rinfo_{region_id}_{key}"))

    kb.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_start"))
    kb.adjust(1) # Кнопки в столбик


    # Главное фото региона
    main_image = region.get("geography", {}).get("image")
    image_path = get_image_source(region_id, main_image)
    
    text = (
        f"📍 *{region['display_name']}*\n\n"
        f"{region.get('geography', {}).get('summary', 'Добро пожаловать в регион!')}\n\n"
        "Выберите раздел для получения информации:"
    )
    await send_and_replace(query, text=text, image_path=image_path, markup=kb.as_markup())


@router.callback_query(F.data.startswith("rinfo_"))
async def region_section(query: CallbackQuery):
    try:
        _, region_id, section_key = query.data.split("_", 2)
    except ValueError:
        await query.answer("Неправильные данные запроса", show_alert=True)
        return

    region = _get_region_data(region_id)
    if not region:
        await query.answer("Регион не найден", show_alert=True)
        return

    section_data = region.get(section_key, {})
    
    title_map = { # Отображение ключей разделов в красивые заголовки
        "geography": "🗺 Общие сведения",
        "resources": "🌿 Природные ресурсы",
        "history": "📜 История",
        "economy": "📈 Экономика",
        "culture": "🎭 Культура и население",
        "sights": "🌟 Достопримечательности"
    }
    title = title_map.get(section_key, section_key.capitalize())

    text_parts = [f"*{title}*\n"]
    summary = section_data.get("summary")
    full_description = section_data.get("full_description")
    facts = section_data.get("facts")

    if summary:
        text_parts.append(summary)
    
    if facts:
        text_parts.append("\n" + "\n".join(f"• {fact}" for fact in facts))

    # Дополнительные детали для "geography"
    if section_key == "geography":
        g = section_data
        if g.get("area"): text_parts.append(f"\n📏 *Площадь:* {g['area']}")
        if g.get("population"): text_parts.append(f"👥 *Население:* {g['population']}")
        if g.get("capital"): text_parts.append(f"🏛 *Столица:* {g['capital']}")
        if g.get("climate"): text_parts.append(f"🌤 *Климат:* {g['climate']}")
    elif section_key == "resources":
        if section_data.get("zapovedniki"):
            text_parts.append(f"\n_Заповедники и нац. парки: {', '.join(section_data['zapovedniki'])}._")
    elif section_key == "culture":
        if section_data.get("ethnic"):
            text_parts.append(f"\n_Этнический состав: {section_data['ethnic']}_")
        if section_data.get("religion"):
            text_parts.append(f"_Основные религии: {section_data['religion']}_")


    text = "\n".join(text_parts)

    image_path = get_image_source(region_id, section_data.get("image"))

    kb = InlineKeyboardBuilder()
    if full_description and len(full_description) > (len(summary or "") + len("\n".join(facts or []))): # Проверяем, есть ли смысл в кнопке "Подробнее"
        kb.add(InlineKeyboardButton(text="📖 Подробнее", callback_data=f"rfull_{region_id}_{section_key}"))
        kb.adjust(1)
    
    # Кнопки навигации всегда внизу
    if section_key == "sights": # Для достопримечательностей своя логика
         kb.row(InlineKeyboardButton(text="🌟 К списку достопримечательностей", callback_data=f"sights_list_{region_id}"))
    else:
        kb.row(InlineKeyboardButton(text="⬅️ В меню региона", callback_data=f"region_{region_id}"))

    await send_and_replace(query, text, image_path, kb.as_markup())


# @router.callback_query(F.data.startswith("rfull_"))
# async def _show_full_description(query: CallbackQuery):
#     try:
#         _, region_id, section_key = query.data.split("_", 2)
#     except ValueError:
#         await query.answer("Неправильные данные запроса", show_alert=True)
#         return

#     region = _get_region_data(region_id)
#     if not region:
#         await query.answer("Регион не найден", show_alert=True)
#         return

#     section_data = region.get(section_key, {})
#     full_description = section_data.get("full_description", "Полное описание отсутствует.")

#     title_map = {
#         "geography": "🗺 Общие сведения (Подробнее)",
#         "resources": "🌿 Природные ресурсы (Подробнее)",
#         "history": "📜 История (Подробнее)",
#         "economy": "📈 Экономика (Подробнее)",
#         "culture": "🎭 Культура и население (Подробнее)"
#     }
#     title = title_map.get(section_key, f"{section_key.capitalize()} (Подробнее)")

#     text = f"*{title}*\n\n{full_description}"
#     image_path = get_image_source(region_id, section_data.get("image"))

#     kb = InlineKeyboardBuilder()
#     kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rinfo_{region_id}_{section_key}"))
#     await send_and_replace(query, text, image_path, kb.as_markup())


# Обработчик для перехода к списку достопримечательностей
@router.callback_query(F.data.startswith("sights_list_"))
async def sights_list_menu(query: CallbackQuery):
    region_id = query.data.split("sights_list_")[1]
    region = _get_region_data(region_id)
    if not region:
        await query.answer("Регион не найден", show_alert=True)
        return

    s = region.get("sights", {})
    items = s.get("items", [])
    if not items:
        text = "Достопримечательности не найдены."
        image_path = get_image_source(region_id, s.get("image"))
        kb = InlineKeyboardBuilder()
        kb.add(InlineKeyboardButton(text="⬅️ В меню региона", callback_data=f"region_{region_id}"))
        await send_and_replace(query, text, image_path, kb.as_markup())
        return

    # Кнопки — каждая достопримечательность
    kb = InlineKeyboardBuilder()
    for i, it in enumerate(items):
        label = it.get("name", f"Пункт {i+1}")
        kb.add(InlineKeyboardButton(text=f"{i+1}. {label}", callback_data=f"sight_{region_id}_{i}_0")) # 0 - начальный индекс страницы достопримечательностей
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="⬅️ В меню региона", callback_data=f"region_{region_id}"))
    
    text = (
        f"🗺 *Достопримечательности {region['display_name']}*\n\n"
        f"{s.get('summary', 'Выберите объект, чтобы посмотреть подробно:')}"
    )
    image_path = get_image_source(region_id, s.get("image")) # Общее фото для раздела Достопримечательности
    await send_and_replace(query, text, image_path, kb.as_markup())


@router.callback_query(F.data.startswith("sight_"))
async def sight_detail(query: CallbackQuery):
    # sight_{region_id}_{index}_{show_full}
    # show_full: 0 - краткое описание, 1 - полное описание
    try:
        _, region_id, idx_str, show_full_str = query.data.split("_", 3)
        idx = int(idx_str)
        show_full = bool(int(show_full_str))
    except Exception:
        await query.answer("Неправильные данные запроса", show_alert=True)
        return

    region = _get_region_data(region_id)
    if not region:
        await query.answer("Регион не найден", show_alert=True)
        return

    items = region.get("sights", {}).get("items", [])
    if idx < 0 or idx >= len(items):
        await query.answer("Достопримечательность не найдена", show_alert=True)
        return

    item = items[idx]
    name = item.get("name", "Достопримечательность")
    
    description = item.get("full_description" if show_full else "short_description", "Описание отсутствует.")
    if not description and not show_full: # Если short_description нет, но есть full
        description = item.get("full_description", "Описание отсутствует.")

    fact = item.get("fact", "")
    address = item.get("address", "")
    hours = item.get("hours", "")
    price = item.get("price", "")

    text_parts = [f"*{name}*\n\n{description}"]
    
    if fact:
        text_parts.append(f"\n_💡 Интересный факт: {fact}_")
    if address:
        text_parts.append(f"📍 *Адрес:* {address}")
    if hours:
        text_parts.append(f"⏱ *Часы работы:* {hours}")
    if price:
        text_parts.append(f"💵 *Стоимость:* {price}")

    text = "\n".join(text_parts)

    image_path = get_image_source(region_id, item.get("image"))

    kb = InlineKeyboardBuilder()

    # Кнопки для детального/полного описания
    if item.get("full_description") and item.get("short_description") and item["full_description"] != item["short_description"]:
        if not show_full:
            kb.add(InlineKeyboardButton(text="📖 Подробнее", callback_data=f"sight_{region_id}_{idx}_1"))
        else:
            kb.add(InlineKeyboardButton(text="⬅️ Свернуть", callback_data=f"sight_{region_id}_{idx}_0"))
        kb.adjust(1) # Размещаем их отдельно

    # Кнопки навигации по достопримечательностям
    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"sight_{region_id}_{idx-1}_0"))
    if idx + 1 < len(items):
        nav_buttons.append(InlineKeyboardButton(text="Следующая ▶️", callback_data=f"sight_{region_id}_{idx+1}_0"))
    if nav_buttons:
        kb.row(*nav_buttons) # Добавляем кнопки в ряд
    
    # Кнопки действия
    action_buttons = []
    # if item.get("audio"): # Если есть аудиогид
    #     action_buttons.append(InlineKeyboardButton(text="🎵 Аудиогид", callback_data=f"audio_{region_id}_{idx}"))
    # if item.get("address"): # Если есть адрес, можно добавить кнопку "Показать на карте"
    #     action_buttons.append(InlineKeyboardButton(text="🗺 На карте", url=f"https://yandex.ru/maps/?text={item['address']}"))
    if action_buttons:
        kb.row(*action_buttons)

    # Кнопки возврата
    kb.row(InlineKeyboardButton(text="🌟 К списку достопримечательностей", callback_data=f"sights_list_{region_id}"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню региона", callback_data=f"region_{region_id}"))

    await send_and_replace(query, text, image_path, kb.as_markup())