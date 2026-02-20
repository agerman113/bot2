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
ZAI_API_KEY = os.getenv('ZAI_API_KEY')  # ожидается формат: {API Key ID}.{secret}

# Настройки Z.ai (можете менять под документацию)
ZAI_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # Часто используемый URL для Zhipu AI
ZAI_MODEL = "glm-4-flash"  # Популярная модель
ZAI_AUTH_HEADER = "Authorization"  # или "api-key"
ZAI_AUTH_PREFIX = "Bearer"  # оставить пустым, если используете "api-key"

def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('😂 Анекдот', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def generate_joke():
    if not ZAI_API_KEY:
        return "❌ Ключ API Z.ai не настроен."

    # Формируем заголовок авторизации
    if ZAI_AUTH_PREFIX:
        auth_value = f"{ZAI_AUTH_PREFIX} {ZAI_API_KEY}"
    else:
        auth_value = ZAI_API_KEY

    headers = {
        ZAI_AUTH_HEADER: auth_value,
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
        logger.info(f"Отправка запроса к {ZAI_API_URL} с моделью {ZAI_MODEL}")
        response = requests.post(ZAI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        # Извлекаем текст ответа (структура как у OpenAI)
        if 'choices' in result and len(result['choices']) > 0:
            joke = result['choices'][0]['message']['content'].strip()
        elif 'response' in result:
            joke = result['response'].strip()
        else:
            joke = str(result)

        if len(joke) > 4000:
            joke = joke[:4000] + "..."

        return joke

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка HTTP запроса: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Тело ответа: {e.response.text}")
        return f"⚠️ Ошибка связи с API: {e}"
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return "⚠️ Не удалось получить анекдот."

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
