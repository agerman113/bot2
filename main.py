import os
import logging
import asyncio
from google import genai
from vkbottle import Bot, Keyboard, KeyboardButtonColor, Text, OpenLink
from vkbottle.dispatch.dispenser import BaseStateGroup

# ======================== ТОКЕНЫ ========================
VK_TOKEN = "vk1.a.B7T79NLqWQjMZtlHbzne5JP1jsC73w6hEoUWe_afiBGGm-feK986ztH-ebkSGj5Bd6qckSX7I2XMmQE4DcBpq2C7ofrNcb29bytWmWzDl7TAz38mY7XyX8qA1ivYhMJm5lW0RCHhXqg9yXyf24leFatY-h_wVHOnqEvFZVjfHonQQRFZZ698ZdL_cxV52970SZhKDa3T2xf8uk0-BpqnAQ"
GEMINI_API_KEY = "AIzaSyAzW2TzaCS14ahwW0-XCZM0bWS36KfaZLc"
REFERRAL_LINK = "https://ad.admitad.com/your-referral-link"
# =========================================================

client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=VK_TOKEN)
logging.basicConfig(level=logging.INFO)

main_keyboard = (
    Keyboard(one_time=False, inline=False)
    .add(Text("🔨 Новая смета"), color=KeyboardButtonColor.PRIMARY)
    .get_json()
)

@bot.on.message()
async def handle_message(message):
    if message.from_id < 0:
        return

    if message.text == "🔨 Новая смета":
        await message.answer("Опишите, что нужно сделать (например: «покрасить стены в комнате 20 м², постелить ламинат, заменить розетки»).", keyboard=main_keyboard)
        return

    await message.answer("⏳ Составляю смету... Это может занять несколько секунд.")

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
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
        )
        answer = response.text
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        answer = "😕 Не удалось получить ответ от ИИ. Попробуйте позже или уточните описание."

    final_answer = f"{answer}\n\n---\n🔗 Для закупки материалов рекомендуем проверенный магазин: {REFERRAL_LINK}"
    await message.answer(final_answer, keyboard=main_keyboard, disable_mentions=True)

if __name__ == "__main__":
    # В vkbottle 4.6.2 используется run_forever(), а не run()
    bot.run_forever()
