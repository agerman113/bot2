import os
import logging
import asyncio
import google.generativeai as genai
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink
from vkbottle.dispatch.states import BaseStateGroup

# ---------- ПОЛУЧЕНИЕ ТОКЕНОВ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ----------
VK_TOKEN = os.getenv("VK_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REFERRAL_LINK = os.getenv("REFERRAL_LINK", "https://ad.admitad.com/your-referral-link")  # опционально

if not VK_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Не заданы VK_TOKEN или GEMINI_API_KEY в переменных окружения")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')  # или 'gemini-pro'

bot = Bot(token=VK_TOKEN)
logging.basicConfig(level=logging.INFO)

# ---------- СОСТОЯНИЯ ----------
class EstimateStates(BaseStateGroup):
    ROOM_TYPE = 0
    AREA = 1
    WORK_TYPE = 2
    AI_DESCRIPTION = 3

# ---------- КЛАВИАТУРЫ (как в предыдущем коде) ----------
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

# ---------- ОБРАБОТЧИКИ (полностью из предыдущего кода) ----------
@bot.on.message()
async def start(message: Message):
    if await bot.state_dispenser.get(message.peer_id):
        return
    await message.answer(
        "Здравствуйте! Я бот строительной компании «РемонтПрофи». Помогу рассчитать стоимость ремонта, подобрать материалы и вызвать специалиста.",
        keyboard=main_keyboard
    )

# ---------- Обычный расчёт ----------
@bot.on.message(text="🧮 Рассчитать смету (обычный)")
async def estimate_start(message: Message):
    await bot.state_dispenser.set(message.peer_id, EstimateStates.ROOM_TYPE)
    await message.answer("Выберите тип помещения:", keyboard=room_keyboard)

# ... (вставьте сюда все остальные обработчики из предыдущего полного кода,
#      они должны быть точно такими же, как я давал ранее) ...

# Для краткости я не копирую их полностью, но вы должны вставить:
# - estimate_room_type
# - estimate_area
# - estimate_work_type
# - ai_estimate_start
# - ai_estimate_process
# - materials
# - portfolio
# - call_measurer

# Важно: в функции materials используйте REFERRAL_LINK вместо глобальной переменной

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    bot.run()
