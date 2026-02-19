import logging
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink
from vkbottle.dispatch.rules.base import StateRule
from vkbottle.dispatch.states import BaseStateGroup
import asyncio

# Токен сообщества ВКонтакте (получаем в настройках сообщества -> Работа с API)
TOKEN = "your_vk_group_token"
# Реферальная ссылка на магазин стройматериалов
REFERRAL_LINK_MATERIALS = "https://ad.admitad.com/your-referral-link"

bot = Bot(token=TOKEN)
logging.basicConfig(level=logging.INFO)

# Определяем состояния для конечного автомата (расчёт сметы)
class EstimateStates(BaseStateGroup):
    ROOM_TYPE = 0
    AREA = 1
    WORK_TYPE = 2

# Клавиатура главного меню
main_keyboard = (
    Keyboard(one_time=False, inline=False)
    .add(Text("🧮 Рассчитать смету"), color=KeyboardButtonColor.PRIMARY)
    .row()
    .add(Text("🛒 Подобрать материалы"), color=KeyboardButtonColor.SECONDARY)
    .row()
    .add(Text("📸 Портфолио"), color=KeyboardButtonColor.SECONDARY)
    .add(Text("📞 Вызвать замерщика"), color=KeyboardButtonColor.PRIMARY)
    .get_json()
)

# Клавиатура для выбора типа помещения
room_keyboard = (
    Keyboard(one_time=True, inline=False)
    .add(Text("Квартира"))
    .add(Text("Дом"))
    .add(Text("Офис"))
    .get_json()
)

# Клавиатура для выбора типа ремонта
work_keyboard = (
    Keyboard(one_time=True, inline=False)
    .add(Text("Косметический"))
    .add(Text("Капитальный"))
    .add(Text("Дизайнерский"))
    .get_json()
)

# Обработчик команды "начать" (любое сообщение, если нет состояния)
@bot.on.message()
async def start(message: Message):
    # Проверяем, не находимся ли мы уже в каком-то состоянии
    if await bot.state_dispenser.get(message.peer_id):
        return
    await message.answer(
        "Здравствуйте! Я бот строительной компании «РемонтПрофи». Помогу рассчитать стоимость ремонта, подобрать материалы и вызвать специалиста.",
        keyboard=main_keyboard
    )

# ---------- Расчёт сметы ----------
@bot.on.message(text="🧮 Рассчитать смету")
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
    # Получаем сохранённые данные
    state_data = await bot.state_dispenser.get(message.peer_id)
    room_type = state_data.payload["room_type"]
    area = state_data.payload["area"]
    work_type = message.text

    # Простой расчёт стоимости
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

# ---------- Подбор материалов с реферальными ссылками ----------
@bot.on.message(text="🛒 Подобрать материалы")
async def materials(message: Message):
    # Создаём клавиатуру со ссылками (OpenLink)
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

# ---------- Портфолио ----------
@bot.on.message(text="📸 Портфолио")
async def portfolio(message: Message):
    # Для фото нужно прикрепить вложение. Проще всего отправить ссылку на альбом.
    await message.answer(
        "Примеры наших работ:\n"
        "https://vk.com/album-123456789_123456789\n"  # замените на реальный альбом
        "Больше фото на сайте: https://example.com/portfolio"
    )

# ---------- Вызов замерщика ----------
@bot.on.message(text="📞 Вызвать замерщика")
async def call_measurer(message: Message):
    # В VK можно запросить номер через специальную кнопку с request_contact,
    # но она доступна только в сообщениях сообщества, если разрешено.
    # Сделаем проще: попросим пользователя написать номер вручную.
    await message.answer(
        "Для вызова замерщика напишите ваш номер телефона, и мы свяжемся с вами в ближайшее время.",
        keyboard=main_keyboard  # можно оставить главное меню
    )
    # Здесь нужно будет обработать ввод номера. Для упрощения сохраним состояние.
    # Но для краткости просто ждём любое сообщение как номер.

# Обработчик для номера (если хотите ловить после команды вызова)
# Но чтобы не усложнять, можно просто собирать все сообщения, не подходящие под другие команды,
# и считать их заявками. Но тогда нужна дополнительная логика.

# Запуск бота
if __name__ == "__main__":
    bot.run()
