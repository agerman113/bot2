import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Настройки
API_TOKEN = 'YOUR_BOT_TOKEN'
REFERRAL_LINK_MATERIALS = 'https://ad.admitad.com/your-referral-link'  # Пример реферальной ссылки на магазин стройматериалов

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Клавиатура главного меню
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton('🧮 Рассчитать смету'))
main_menu.add(KeyboardButton('🛒 Подобрать материалы'))
main_menu.add(KeyboardButton('📸 Портфолио'))
main_menu.add(KeyboardButton('📞 Вызвать замерщика'))

# Состояния для сметы
class EstimateState(StatesGroup):
    room_type = State()      # тип помещения
    area = State()           # площадь
    work_type = State()      # вид работ

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "Здравствуйте! Я бот строительной компании «РемонтПрофи». Помогу рассчитать стоимость ремонта, подобрать материалы и вызвать специалиста.",
        reply_markup=main_menu
    )

# ---------- Расчёт сметы ----------
@dp.message_handler(lambda message: message.text == '🧮 Рассчитать смету')
async def estimate_start(message: types.Message):
    await message.answer("Выберите тип помещения:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton('Квартира'), KeyboardButton('Дом'), KeyboardButton('Офис')
    ))
    await EstimateState.room_type.set()

@dp.message_handler(state=EstimateState.room_type)
async def estimate_room_type(message: types.Message, state: FSMContext):
    await state.update_data(room_type=message.text)
    await message.answer("Укажите площадь в квадратных метрах:", reply_markup=types.ReplyKeyboardRemove())
    await EstimateState.area.set()

@dp.message_handler(state=EstimateState.area)
async def estimate_area(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (только цифры).")
        return
    await state.update_data(area=int(message.text))
    # Выбор типа работ
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton('Косметический'), KeyboardButton('Капитальный'), KeyboardButton('Дизайнерский')
    )
    await message.answer("Выберите вид ремонта:", reply_markup=markup)
    await EstimateState.work_type.set()

@dp.message_handler(state=EstimateState.work_type)
async def estimate_work_type(message: types.Message, state: FSMContext):
    await state.update_data(work_type=message.text)
    data = await state.get_data()
    # Простой расчёт (для примера)
    base_price = 0
    if data['work_type'] == 'Косметический':
        base_price = 3000
    elif data['work_type'] == 'Капитальный':
        base_price = 7000
    elif data['work_type'] == 'Дизайнерский':
        base_price = 12000
    total = data['area'] * base_price
    await message.answer(
        f"💰 Примерная стоимость ремонта:\n"
        f"Помещение: {data['room_type']}\n"
        f"Площадь: {data['area']} м²\n"
        f"Вид ремонта: {data['work_type']}\n"
        f"ИТОГО: {total:,} руб.\n\n"
        f"*Точная смета после выезда замерщика.",
        reply_markup=main_menu
    )
    await state.finish()

# ---------- Подбор материалов с реферальной ссылкой ----------
@dp.message_handler(lambda message: message.text == '🛒 Подобрать материалы')
async def materials(message: types.Message):
    # Инлайн-кнопки с категориями материалов
    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton('Обои', url=REFERRAL_LINK_MATERIALS),
        InlineKeyboardButton('Краска', url=REFERRAL_LINK_MATERIALS),
        InlineKeyboardButton('Плитка', url=REFERRAL_LINK_MATERIALS),
        InlineKeyboardButton('Ламинат', url=REFERRAL_LINK_MATERIALS),
        InlineKeyboardButton('Сантехника', url=REFERRAL_LINK_MATERIALS),
        InlineKeyboardButton('Инструменты', url=REFERRAL_LINK_MATERIALS)
    )
    await message.answer(
        "Выберите категорию материалов для покупки (цены и наличие на сайте партнёра):",
        reply_markup=inline_kb
    )

# ---------- Портфолио ----------
@dp.message_handler(lambda message: message.text == '📸 Портфолио')
async def portfolio(message: types.Message):
    # Здесь можно прислать фото (media group) или ссылку на альбом
    # Для примера отправим одно фото из интернета
    await bot.send_photo(
        chat_id=message.chat.id,
        photo='https://example.com/photo1.jpg',
        caption='Ремонт квартиры 45 м² в современном стиле'
    )
    await message.answer("Больше примеров работ на нашем сайте: https://example.com/portfolio")

# ---------- Вызов замерщика ----------
@dp.message_handler(lambda message: message.text == '📞 Вызвать замерщика')
async def call_measurer(message: types.Message):
    # Собираем контакт (в данном случае просто номер телефона через контактную кнопку)
    contact_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton('📱 Отправить номер телефона', request_contact=True)
    )
    await message.answer(
        "Для вызова замерщика нажмите кнопку ниже и отправьте ваш номер телефона.\n"
        "Мы перезвоним в течение 15 минут.",
        reply_markup=contact_keyboard
    )

@dp.message_handler(content_types=types.ContentType.CONTACT)
async def handle_contact(message: types.Message):
    contact = message.contact
    # Здесь можно сохранить заявку в БД или отправить менеджеру
    # Для примера просто ответим пользователю
    await message.answer(
        f"Спасибо, {contact.first_name}! Ваш номер {contact.phone_number} принят. Менеджер свяжется с вами в ближайшее время.",
        reply_markup=main_menu
    )
    # Также можно отправить уведомление админу (например, в личку)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"Новая заявка на замер: {contact.first_name} {contact.phone_number}")

# ---------- Запуск ----------
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
