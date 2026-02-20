import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
import logging
from zai import ZaiClient

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Чтение переменных окружения
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
GROUP_ID = os.getenv('VK_GROUP_ID')
ZAI_API_KEY = os.getenv('ZAI_API_KEY')

# Настройка Z.ai клиента
if ZAI_API_KEY:
    zai_client = ZaiClient(api_key=ZAI_API_KEY)
    logger.info("Z.ai клиент создан")
else:
    zai_client = None
    logger.error("ZAI_API_KEY не задан!")

def get_keyboard():
    """Клавиатура с одной кнопкой для анекдота"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('😂 Анекдот', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def generate_joke():
    """Запрос к Z.ai на генерацию анекдота"""
    try:
        # Подготовка сообщения для модели
        messages = [
            {"role": "system", "content": "Ты - дружелюбный помощник, который рассказывает смешные анекдоты."},
            {"role": "user", "content": "Расскажи короткий смешной анекдот на русском языке. Только текст анекдота, без пояснений."}
        ]
        
        # Вызов API через SDK
        response = zai_client.chat.completions.create(
            model="glm-4.7-flash",  # Можно также использовать "glm-4.7"
            messages=messages,
            temperature=0.9,
            max_tokens=500
        )
        
        joke = response.choices[0].message.content.strip()
        
        # Обрезаем, если слишком длинный (лимит ВК ~4096 символов)
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

    logger.info("Бот анекдотов (Z.ai) запущен!")

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            msg = event.obj.message
            user_id = msg['from_id']
            text = msg.get('text', '').lower()

            # Если нет клиента Z.ai – уведомляем
            if not zai_client:
                vk.messages.send(
                    user_id=user_id,
                    message="🤖 Генератор анекдотов временно недоступен (нет API ключа Z.ai).",
                    random_id=0
                )
                continue

            # Проверяем, хочет ли пользователь анекдот
            if 'анекдот' in text or text == '😂 анекдот':
                # Генерируем анекдот
                joke = generate_joke()
                vk.messages.send(
                    user_id=user_id,
                    message=f"😂 *Анекдот:*\n\n{joke}",
                    keyboard=get_keyboard(),
                    random_id=0
                )
            else:
                # Если сообщение не про анекдот – предлагаем нажать кнопку
                vk.messages.send(
                    user_id=user_id,
                    message="Привет! Я умею рассказывать анекдоты. Нажми кнопку ниже.",
                    keyboard=get_keyboard(),
                    random_id=0
                )

if __name__ == '__main__':
    main()
