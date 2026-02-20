import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
import logging
from google import genai

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Чтение переменных окружения
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
GROUP_ID = os.getenv('VK_GROUP_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Настройка Gemini
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("Gemini клиент создан")
else:
    genai_client = None
    logger.error("GEMINI_API_KEY не задан!")

def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('😂 Анекдот', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def generate_joke():
    try:
        prompt = "Расскажи короткий смешной анекдот на русском языке. Без лишних слов, только текст анекдота."
        # ИСПРАВЛЕНО: используем актуальную модель
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash-exp',  # <-- Новая модель
            contents=prompt
        )
        joke = response.text.strip()
        if len(joke) > 4000:
            joke = joke[:4000] + "..."
        return joke
    except Exception as e:
        logger.error(f"Ошибка при генерации анекдота: {e}")
        return "Не удалось придумать анекдот. Попробуй ещё раз позже."

def main():
    if not VK_TOKEN or not GROUP_ID:
        logger.error("Не заданы VK_TOKEN или GROUP_ID")
        return

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)

    logger.info("Бот анекдотов запущен!")

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.obj.message
            user_id = msg['from_id']
            text = msg.get('text', '').lower()

            if not genai_client:
                vk.messages.send(
                    user_id=user_id,
                    message="🤖 ИИ-генератор временно недоступен (нет API ключа).",
                    random_id=0
                )
                continue

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
