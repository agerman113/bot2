import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
import logging
import requests
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Чтение переменных окружения
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
GROUP_ID = os.getenv('VK_GROUP_ID')
ZAI_API_KEY = os.getenv('ZAI_API_KEY')

# Константы для Z.ai API
# Уточните endpoint у провайдера. Обычно это:
ZAI_API_URL = "https://api.z.ai/v1/chat/completions"   # или другой URL, если указан в документации
ZAI_MODEL = "glm-4.7-flash"   # или "glm-4.7", "glm-4-plus" и т.д. – выберите нужную

def get_keyboard():
    """Клавиатура с одной кнопкой для анекдота"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('😂 Анекдот', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def generate_joke():
    """Запрос к Z.ai на генерацию анекдота через HTTP"""
    if not ZAI_API_KEY:
        return "❌ Ключ API Z.ai не настроен."

    headers = {
        "Authorization": f"Bearer {ZAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": ZAI_MODEL,
        "messages": [
            {"role": "system", "content": "Ты - дружелюбный помощник, который рассказывает смешные анекдоты на русском языке."},
            {"role": "user", "content": "Расскажи короткий смешной анекдот. Только текст анекдота, без пояснений."}
        ],
        "temperature": 0.9,
        "max_tokens": 500
    }

    try:
        response = requests.post(ZAI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # выбросит исключение при HTTP ошибке

        result = response.json()
        joke = result['choices'][0]['message']['content'].strip()

        # Обрезаем, если слишком длинный (лимит ВК ~4096 символов)
        if len(joke) > 4000:
            joke = joke[:4000] + "..."

        return joke

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка HTTP запроса: {e}")
        return "⚠️ Не удалось связаться с сервером Z.ai. Попробуйте позже."
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка парсинга ответа: {e}, ответ: {response.text if 'response' in locals() else 'нет ответа'}")
        return "⚠️ Получен некорректный ответ от Z.ai."

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

            # Проверяем, хочет ли пользователь анекдот
            if 'анекдот' in text or text == '😂 анекдот':
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
