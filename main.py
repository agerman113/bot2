import logging
from vkbottle import Bot

# Токен VK (вставьте свой)
VK_TOKEN = "vk1.a.B7T79NLqWQjMZtlHbzne5JP1jsC73w6hEoUWe_afiBGGm-feK986ztH-ebkSGj5Bd6qckSX7I2XMmQE4DcBpq2C7ofrNcb29bytWmWzDl7TAz38mY7XyX8qA1ivYhMJm5lW0RCHhXqg9yXyf24leFatY-h_wVHOnqEvFZVjfHonQQRFZZ698ZdL_cxV52970SZhKDa3T2xf8uk0-BpqnAQ"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создаём бота
bot = Bot(token=VK_TOKEN)

# Обработчик всех сообщений (без аннотации типа)
@bot.on.message()
async def echo_handler(message):
    # Игнорируем сообщения от самого бота (чтобы не зациклиться)
    if message.from_id < 0:
        return
    # Отвечаем простым текстом
    await message.answer(f"Привет! Бот работает. Ты написал: {message.text}")

# Запуск бота (для vkbottle 4.6.2)
if __name__ == "__main__":
    bot.run_forever()
