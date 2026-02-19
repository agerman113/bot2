import logging
import asyncio
import google.generativeai as genai
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink
from vkbottle.dispatch.rules.base import StateRule
from vkbottle.dispatch.states import BaseStateGroup

# ---------- НАСТРОЙКИ ----------
VK_TOKEN = "ВАШ_НОВЫЙ_VK_ТОКЕН"            # замените на новый токен VK
GEMINI_API_KEY = "AIzaSyAzW2TzaCS14ahwW0-XCZM0bWS36KfaZLc"  # ваш ключ (держите в секрете!)
REFERRAL_LINK_MATERIALS = "https://ad.admitad.com/your-referral-link"  # реферальная ссылка

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')  # или 'gemini-pro', если доступно

bot = Bot(token=VK_TOKEN)
logging.basicConfig(level=logging.INFO)

# ---------- СОСТОЯНИЯ ----------
class EstimateStates(BaseStateGroup):
    ROOM_TYPE = 0
    AREA = 1
    WORK_TYPE = 2
    AI_DESCRIPTION = 3   # новое состояние для ввода описания

# ---------- КЛАВИАТУРЫ ----------
main_keyboard = (
    Keyboard(one_time=False, inline=False)
    .add(Text("🧮 Рассчитать смету (обычный)"), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("🤖 Помощь ИИ в смете"), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("🛒 Подобрать материалы"), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Text("📸 Портфолио"), color=KeyboardButtonColor.SECONDARY)
    .add(Text("📞 Вызвать замерщика"), color=KeyboardButtonColor.PRIMARY)
    .get_json()
)

room_keyboard = (
    Keyboard(one_time=True, inline=False)
    .add(Text("Квартира"))
    .add(Text("Дом"))
    .add(Text("Офис"))
    .get_json()
)

work_keyboard = (
    Keyboard(one_time=True, inline=False)
    .add(Text("Косметический"))
    .add(Text("Капитальный"))
    .add(Text("Дизайнерский"))
    .get_json()
)

# ---------- ОСНОВНЫЕ ОБРАБОТЧИКИ ----------
@bot.on.message()
async def start(message: Message):
    if await bot.state_dispenser.get(message.peer_id):
        return
    await message.answer(
        "Здравствуйте! Я бот строительной компании «РемонтПрофи». Помогу рассчитать стоимость ремонта, подобрать материалы и вызвать специалиста.",
        keyboard=main_keyboard
    )

# ---------- ОБЫЧНЫЙ РАСЧЁТ СМЕТЫ ----------
@bot.on.message(text="🧮 Рассчитать смету (обычный)")
async def estimate_start(message: Message):
    await bot.state_dispenser.set(message.peer_id, EstimateStates.ROOM_TYPE)
    await message.answer("Выберите тип помещения:", keyboard=room_keyboard)

@bot.on.message(state=EstimateStates.ROOM_TYPE)
async def estimate_room_type(message: Message):
    if message.text not in ["Квартира", "Дом", "Офис"]:
        await message.answer("Пожалуйста, выберите один из вариантов на клавиатуре.")
        return
    await bot.state_dispenser.set(message.peer_id, EstimateStates.AREA, room_type=message.text)
    await message.answer("Укажите площадь в квадратных метрах (только число):", keyboard=Keyboard.get_empty())

@bot.on.message(state=EstimateStates.AREA)
async def estimate_area(message: Message):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (только цифры).")
        return
    area = int(message.text)
    await bot.state_dispenser.set(message.peer_id, EstimateStates.WORK_TYPE, area=area)
    await message.answer("Выберите вид ремонта:", keyboard=work_keyboard)

@bot.on.message(state=EstimateStates.WORK_TYPE)
async def estimate_work_type(message: Message):
    if message.text not in ["Косметический", "Капитальный", "Дизайнерский"]:
        await message.answer("Пожалуйста, выберите вид ремонта на клавиатуре.")
        return
    state_data = await bot.state_dispenser.get(message.peer_id)
    room_type = state_data.payload["room_type"]
    area = state_data.payload["area"]
    work_type = message.text

    base_price = {"Косметический": 3000, "Капитальный": 7000, "Дизайнерский": 12000}[work_type]
    total = area * base_price

    await message.answer(
        f"💰 Примерная стоимость ремонта:\n"
        f"Помещение: {room_type}\n"
        f"Площадь: {area} м²\n"
        f"Вид ремонта: {work_type}\n"
        f"ИТОГО: {total:,} руб.\n\n"
        f"*Точная смета после выезда замерщика.",
        keyboard=main_keyboard
    )
    await bot.state_dispenser.delete(message.peer_id)

# ---------- НОВОЕ: ПОМОЩЬ ИИ В СОСТАВЛЕНИИ СМЕТЫ ----------
@bot.on.message(text="🤖 Помощь ИИ в смете")
async def ai_estimate_start(message: Message):
    await bot.state_dispenser.set(message.peer_id, EstimateStates.AI_DESCRIPTION)
    await message.answer(
        "Опишите словами, что вы хотите сделать (например: «нужно сделать ремонт в ванной 4 м², положить плитку на стены и пол, заменить унитаз и раковину»).",
        keyboard=Keyboard.get_empty()
    )

@bot.on.message(state=EstimateStates.AI_DESCRIPTION)
async def ai_estimate_process(message: Message):
    user_text = message.text
    await message.answer("⏳ Генерирую смету с помощью ИИ... Это займёт несколько секунд.")

    # Промпт для Gemini
    prompt = f"""
Ты — помощник в составлении строительных смет. На основе описания клиента составь примерную смету ремонта.

Описание клиента: {user_text}

Формат ответа:
- Перечисли основные виды работ.
- Для каждого вида работ укажи примерный объём (в м², шт. и т.п.) и примерную стоимость (работа + материалы).
- В конце укажи общую примерную сумму (в рублях).
- Добавь пару советов по выбору материалов.

Ответ должен быть понятным, структурированным, без лишних отступлений.
"""

    try:
        # Запускаем запрос к Gemini в отдельном потоке, чтобы не блокировать бота
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
        answer = response.text
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        answer = "😕 Не удалось получить ответ от ИИ. Попробуйте позже или опишите короче."

    # Отправляем результат пользователю и возвращаем в главное меню
    await message.answer(
        f"🧠 **Смета от ИИ**\n\n{answer}\n\n---\nДля закупки материалов рекомендуем проверенный магазин: {REFERRAL_LINK_MATERIALS}",
        keyboard=main_keyboard,
        disable_mentions=True
    )
    await bot.state_dispenser.delete(message.peer_id)

# ---------- ПОДБОР МАТЕРИАЛОВ ----------
@bot.on.message(text="🛒 Подобрать материалы")
async def materials(message: Message):
    materials_keyboard = (
        Keyboard(inline=True)
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Обои"))
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Краска"))
        .row()
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Плитка"))
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Ламинат"))
        .row()
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Сантехника"))
        .add(OpenLink(REFERRAL_LINK_MATERIALS, "Инструменты"))
        .get_json()
    )
    await message.answer(
        "Выберите категорию материалов (откроется сайт партнёра):",
        keyboard=materials_keyboard
    )

# ---------- ПОРТФОЛИО ----------
@bot.on.message(text="📸 Портфолио")
async def portfolio(message: Message):
    await message.answer(
        "Примеры наших работ:\n"
        "https://vk.com/album-123456789_123456789\n"  # замените на реальный альбом
        "Больше фото на сайте: https://example.com/portfolio"
    )

# ---------- ВЫЗОВ ЗАМЕРЩИКА ----------
@bot.on.message(text="📞 Вызвать замерщика")
async def call_measurer(message: Message):
    await message.answer(
        "Для вызова замерщика напишите ваш номер телефона, и мы свяжемся с вами в ближайшее время.",
        keyboard=main_keyboard
    )
    # Здесь можно было бы также добавить состояние для сбора номера,
    # но для простоты оставим так. При желании доработайте.

# Запуск бота
if __name__ == "__main__":
    bot.run()
