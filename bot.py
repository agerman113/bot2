import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
import logging
from openai import OpenAI

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Чтение переменных окружения
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
GROUP_ID = os.getenv('VK_GROUP_ID')
QWEN_API_KEY = os.getenv('QWEN_API_KEY')  # ключ от DashScope

# Инициализация клиента Qwen
if QWEN_API_KEY:
    try:
        client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # endpoint Qwen
        )
        logger.info("Qwen клиент создан")
    except Exception as e:
        logger.error(f"Ошибка при создании клиента Qwen: {e}")
        client = None
else:
    client = None
    logger.error("QWEN_API_KEY не задан!")

def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('😂 Анекдот', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def generate_joke():
    if not client:
        return "❌ API-клиент не инициализирован. Проверьте ключ Qwen."

    try:
        response = client.chat.completions.create(
            model="qwen-turbo",  # бесплатная модель, можно также "qwen-plus"
            messages=[
                {"role": "system", "content": "Ты - дружелюбный помощник, который рассказывает смешные анекдоты на русском языке. Отвечай только текстом анекдота, без пояснений."},
                {"role": "user", "content": "Расскажи короткий смешной анекдот."}
            ],
            temperature=0.9,
            max_tokens=500
        )

        joke = response.choices[0].message.content.strip()
        if len(joke) > 4000:
            joke = joke[:4000] + "..."
        return joke

    except Exception as e:
        logger.error(f"Ошибка при генерации анекдота: {e}")
        return f"⚠️ Ошибка: {e}"

def main():
    if not VK_TOKEN or not GROUP_ID:
        logger.error("Не заданы VK_TOKEN или GROUP_ID")
        return

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)

    logger.info("Бот анекдотов (Qwen) запущен!")

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.obj.message
            user_id = msg['from_id']
            text = msg.get('text', '').lower()

            if 'анекдот' in text or text == '😂 анекдот':
                joke = generate_joke()
                vk.messages.send(
                    user_id=user_id,
                    message=f"😂 *Анекдот:*\n\n{joke}",
                    keyboard=get_keyboard(),
                    random_id=0
                )
            else:
                vk.messages.send(
                    user_id=user_id,
                    message="Привет! Я умею рассказывать анекдоты. Нажми кнопку ниже.",
                    keyboard=get_keyboard(),
                    random_id=0
                )

if __name__ == '__main__':
    main()
