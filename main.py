import os
import logging
import asyncio
from google import genai
from vkbottle import Bot, Keyboard, KeyboardButtonColor, Text, OpenLink
from vkbottle.dispatch.dispenser import BaseStateGroup  # не используется, но оставим для совместимости

# ======================== ТОКЕНЫ (ВСТАВЬТЕ СВОИ) ========================
VK_TOKEN = "vk1.a.B7T79NLqWQjMZtlHbzne5JP1jsC73w6hEoUWe_afiBGGm-feK986ztH-ebkSGj5Bd6qckSX7I2XMmQE4DcBpq2C7ofrNcb29bytWmWzDl7TAz38mY7XyX8qA1ivYhMJm5lW0RCHhXqg9yXyf24leFatY-h_wVHOnqEvFZVjfHonQQRFZZ698ZdL_cxV52970SZhKDa3T2xf8uk0-BpqnAQ"
GEMINI_API_KEY = "AIzaSyAzW2TzaCS14ahwW0-XCZM0bWS36KfaZLc"
REFERRAL_LINK = "https://ad.admitad.com/your-referral-link"   # замените на свою партнёрскую ссылку
# =========================================================================

# Инициализация Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Инициализация VK бота
bot = Bot(token=VK_TOKEN)
logging.basicConfig(level=logging.INFO)

# Простая клавиатура с одной кнопкой (можно убрать, если не нужна)
main_keyboard = (
    Keyboard(one_time=False, inline=False)
    .add(Text("🔨 Новая смета"), color=KeyboardButtonColor.PRIMARY)
    .get_json()
)

@bot.on.message()
async def handle_message(message):
    """Обрабатывает любое сообщение от пользователя"""
    # Игнорируем служебные сообщения (например, от самого бота)
    if message.from_id < 0:
        return

    # Если пользователь нажал кнопку "Новая смета" – просто ждём описание
    if message.text == "🔨 Новая смета":
        await message.answer("Опишите, что нужно сделать (например: «покрасить стены в комнате 20 м², постелить ламинат, заменить розетки»).", keyboard=main_keyboard)
        return

    # Если текст не команда – считаем его описанием ремонта
    await message.answer("⏳ Составляю смету... Это может занять несколько секунд.")

    # Промпт для Gemini
    prompt = f"""
Ты – профессиональный сметчик в строительстве. На основе описания клиента составь подробную смету.

Описание: {message.text}

Формат ответа (точно следуй этому формату):
1. Перечисли все необходимые работы и материалы.
2. Для каждой позиции укажи:
   - Наименование
   - Единицу измерения (м², шт., пог.м и т.д.)
   - Количество
   - Цену за единицу (в рублях)
   - Общую стоимость
3. В конце укажи общую сумму (в рублях).
4. Добавь краткие рекомендации.

Ответ должен быть понятным, структурированным, без лишних пояснений. Используй только русский язык.
"""

    try:
        # Запрос к Gemini (асинхронно в потоке)
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model='gemini-1.5-flash',   # можно заменить на другую модель
                contents=prompt
            )
        )
        answer = response.text
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        answer = "😕 Не удалось получить ответ от ИИ. Попробуйте позже или уточните описание."

    # Добавляем реферальную ссылку в конец
    final_answer = f"{answer}\n\n---\n🔗 Для закупки материалов рекомендуем проверенный магазин: {REFERRAL_LINK}"

    # Отправляем результат
    await message.answer(final_answer, keyboard=main_keyboard, disable_mentions=True)

if __name__ == "__main__":
    bot.run()
