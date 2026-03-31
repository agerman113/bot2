import os
import time
import logging
import feedparser
import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
import vk_api
from vk_api.upload import VkUpload

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

class VKYouTubeReposter:
    def __init__(self):
        self.vk_token = os.getenv("VK_GROUP_TOKEN")
        self.vk_group_id = os.getenv("VK_GROUP_ID")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        self.check_interval = int(os.getenv("CHECK_INTERVAL", 600))
        self.channel_ids = [ch.strip() for ch in os.getenv("CHANNEL_IDS", "").split(",") if ch.strip()]
        self.ad_text = os.getenv("AD_TEXT", "Узнай, как зарабатывать на партнёрских программах → https://vk.me/1onesis")

        if not self.channel_ids:
            logging.error("Не указаны CHANNEL_IDS в .env. Бот остановлен.")
            raise ValueError("CHANNEL_IDS is empty")

        # Инициализация VK
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()
        self.upload = VkUpload(self.vk_session)

        # Инициализация OpenRouter (через OpenAI SDK)
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
        )

        # Загружаем список уже обработанных видео
        self.processed_videos = self.load_processed_videos()

    def load_processed_videos(self):
        """Загружает ID обработанных видео из файла"""
        if os.path.exists("processed.txt"):
            with open("processed.txt", "r") as f:
                return set(line.strip() for line in f)
        return set()

    def save_processed_video(self, video_id):
        """Сохраняет ID видео в файл"""
        with open("processed.txt", "a") as f:
            f.write(f"{video_id}\n")
        self.processed_videos.add(video_id)

    def get_latest_video_from_channel(self, channel_id):
        """Получает последнее видео с YouTube канала через RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                logging.warning(f"Нет записей в RSS для канала {channel_id}")
                return None

            latest = feed.entries[0]
            video_id = latest.id.split(":")[-1]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            title = latest.title
            return {"id": video_id, "url": video_url, "title": title}
        except Exception as e:
            logging.error(f"Ошибка получения RSS для {channel_id}: {e}")
            return None

    def download_video(self, url, output_path="temp_video.mp4"):
        """Скачивает видео с YouTube через yt-dlp"""
        try:
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logging.info(f"Видео скачано: {url}")
            return output_path
        except Exception as e:
            logging.error(f"Ошибка скачивания видео: {e}")
            return None

    def generate_description(self, video_title, video_url):
        """Генерирует описание через OpenRouter (с обработкой rate limit)"""
        prompt = f"""
        Напиши короткое и привлекательное описание для смешного видео, которое будет опубликовано в паблике ВКонтакте.
        Оригинальное название видео: "{video_title}"
        Ссылка на видео: {video_url}
        
        Требования:
        - Язык: русский
        - Длина: 2-3 предложения
        - Добавь 3-5 хэштегов (#юмор, #смешноевидео и т.п.)
        - Используй эмодзи
        - Не упоминай рекламу (она будет добавлена отдельно)
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=200,
                )
                ai_text = response.choices[0].message.content.strip()
                # Добавляем рекламный текст в конец описания
                full_description = f"{ai_text}\n\n{self.ad_text}"
                return full_description
            except RateLimitError:
                wait = 20 * (attempt + 1)  # 20, 40, 60 секунд
                logging.warning(f"Превышен лимит OpenRouter. Ждём {wait} сек...")
                time.sleep(wait)
            except Exception as e:
                logging.error(f"Ошибка AI: {e}")
                if attempt == max_retries - 1:
                    # fallback описание без AI
                    fallback = f"😄 Смешное видео: {video_title}\n\n#юмор #приколы #смешноевидео\n\n{self.ad_text}"
                    return fallback
        # Если все попытки не удались
        return f"Смешное видео: {video_title}\n\n{self.ad_text}"

    def post_to_vk(self, video_path, description):
        """Публикует видео на стену сообщества ВК"""
        try:
            video_data = self.upload.video(
                video_file=video_path,
                name=os.path.basename(video_path),
                description=description,
                group_id=int(self.vk_group_id),
                is_private=0,
                wallpost=1
            )
            video_url = f"https://vk.com/video{video_data['owner_id']}_{video_data['video_id']}"
            logging.info(f"Видео опубликовано: {video_url}")
            return True
        except Exception as e:
            logging.error(f"Ошибка публикации в VK: {e}")
            return False

    def process_new_video(self, channel_id, video_info):
        """Полный цикл обработки нового видео"""
        logging.info(f"Новое видео на канале {channel_id}: {video_info['title']} ({video_info['url']})")
        video_file = self.download_video(video_info["url"])
        if not video_file:
            return False

        description = self.generate_description(video_info["title"], video_info["url"])
        success = self.post_to_vk(video_file, description)

        # Удаляем временный файл
        if os.path.exists(video_file):
            os.remove(video_file)

        if success:
            self.save_processed_video(video_info["id"])
            logging.info(f"Видео {video_info['id']} обработано успешно")
        else:
            logging.error(f"Не удалось обработать видео {video_info['id']}")
        return success

    def run(self):
        """Основной бесконечный цикл мониторинга"""
        logging.info("🚀 Бот запущен. Мониторинг каналов: " + ", ".join(self.channel_ids))
        while True:
            try:
                for channel_id in self.channel_ids:
                    logging.info(f"Проверка канала {channel_id}...")
                    latest = self.get_latest_video_from_channel(channel_id)
                    if latest and latest["id"] not in self.processed_videos:
                        self.process_new_video(channel_id, latest)
                    else:
                        logging.info(f"Новых видео на канале {channel_id} нет")
                logging.info(f"Ожидание {self.check_interval} секунд...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logging.info("Бот остановлен пользователем")
                break
            except Exception as e:
                logging.error(f"Неожиданная ошибка: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = VKYouTubeReposter()
    bot.run()
