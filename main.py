import os
import time
import logging
import feedparser
import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
import vk_api
from vk_api.upload import VkUpload
import requests

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

class YouTubeShortsToVKClipsBot:
    def __init__(self):
        self.vk_token = os.getenv("VK_GROUP_TOKEN")
        self.vk_group_id = int(os.getenv("VK_GROUP_ID"))
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        self.check_interval = int(os.getenv("CHECK_INTERVAL", 600))
        self.channel_ids = [ch.strip() for ch in os.getenv("CHANNEL_IDS", "").split(",") if ch.strip()]
        self.ad_text = os.getenv("AD_TEXT", "Узнай, как зарабатывать на партнёрских программах → https://vk.me/1onesis")
        self.max_duration_seconds = int(os.getenv("MAX_DURATION_SECONDS", 60))  # Shorts обычно до 60 сек

        if not self.channel_ids:
            raise ValueError("CHANNEL_IDS is empty")

        # VK
        self.vk_session = vk_api.VkApi(token=self.vk_token)
        self.vk = self.vk_session.get_api()
        self.upload = VkUpload(self.vk_session)

        # OpenRouter
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
        )

        self.processed_videos = self.load_processed_videos()

    def load_processed_videos(self):
        if os.path.exists("processed.txt"):
            with open("processed.txt", "r") as f:
                return set(line.strip() for line in f)
        return set()

    def save_processed_video(self, video_id):
        with open("processed.txt", "a") as f:
            f.write(f"{video_id}\n")
        self.processed_videos.add(video_id)

    def get_latest_video_from_channel(self, channel_id):
        """Получает последнее видео с канала через RSS"""
        try:
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                return None
            latest = feed.entries[0]
            video_id = latest.id.split(":")[-1]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            title = latest.title
            return {"id": video_id, "url": video_url, "title": title}
        except Exception as e:
            logging.error(f"RSS error {channel_id}: {e}")
            return None

    def get_video_info(self, url):
        """Получает метаданные: длительность, ширина, высота"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get('duration', 0)
                width = info.get('width')
                height = info.get('height')
                # Если нет ширины/высоты, пробуем из форматов
                if not width or not height:
                    formats = info.get('formats', [])
                    for f in formats:
                        if f.get('width') and f.get('height'):
                            width = f['width']
                            height = f['height']
                            break
                return duration, width, height
        except Exception as e:
            logging.error(f"Ошибка получения метаданных: {e}")
            return 0, None, None

    def is_eligible_short(self, url):
        """Проверяет, подходит ли видео: вертикальное и длительность <= MAX_DURATION_SECONDS"""
        duration, width, height = self.get_video_info(url)
        if duration is None or width is None or height is None:
            logging.warning(f"Не удалось определить параметры видео {url}, пропускаем")
            return False
        is_vertical = height > width if width and height else False
        is_short = duration <= self.max_duration_seconds
        logging.info(f"Видео: длит={duration}с, {width}x{height}, верт={is_vertical}, short={is_short}")
        return is_vertical and is_short

    def download_video(self, url, output_path="temp_video.mp4"):
        """Скачивает видео в mp4"""
        try:
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return output_path
        except Exception as e:
            logging.error(f"Download error: {e}")
            return None

    def generate_description(self, video_title, video_url):
        prompt = f"""
        Напиши короткое и привлекательное описание для смешного вертикального короткого видео (YouTube Shorts), которое будет опубликовано в VK Клипах.
        Оригинальное название видео: "{video_title}"
        Ссылка на видео: {video_url}
        
        Требования:
        - Язык: русский
        - Длина: 2-3 предложения
        - Добавь 3-5 хэштегов (#юмор #shorts #вертикальноевидео и т.п.)
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
                full_description = f"{ai_text}\n\n{self.ad_text}"
                return full_description
            except RateLimitError:
                wait = 20 * (attempt + 1)
                logging.warning(f"Rate limit, ждём {wait}с")
                time.sleep(wait)
            except Exception as e:
                logging.error(f"AI error: {e}")
                if attempt == max_retries - 1:
                    return f"😄 Смешной Shorts: {video_title}\n\n#юмор #shorts\n\n{self.ad_text}"
        return f"Смешное видео: {video_title}\n\n{self.ad_text}"

    def upload_to_vk_clip(self, video_path, title, description):
        """Загружает видео как VK Клип (is_clip=1)"""
        try:
            # Получаем сервер для загрузки клипа
            save_params = {
                "name": title[:200],  # ограничение длины
                "description": description[:1000],
                "is_clip": 1,        # ключевой параметр для клипов
                "group_id": self.vk_group_id,
                "wallpost": 0,       # не публиковать на стену, только в клипы
            }
            # Метод video.save возвращает upload_url
            save_response = self.vk.video.save(**save_params)
            upload_url = save_response['upload_url']
            owner_id = save_response['owner_id']
            video_id = save_response['video_id']

            # Загружаем файл по upload_url
            with open(video_path, 'rb') as f:
                files = {'video_file': f}
                response = requests.post(upload_url, files=files)
                response.raise_for_status()

            # Подтверждаем загрузку (можно не делать, VK сам обработает)
            logging.info(f"Клип загружен: owner_id={owner_id}, video_id={video_id}")
            clip_url = f"https://vk.com/clip{owner_id}_{video_id}"
            return clip_url
        except Exception as e:
            logging.error(f"Ошибка загрузки клипа VK: {e}")
            return None

    def process_short(self, channel_id, video_info):
        logging.info(f"Новый Shorts: {video_info['title']} ({video_info['url']})")

        # Проверяем eligibility (вертикальность и длительность)
        if not self.is_eligible_short(video_info["url"]):
            logging.info(f"Видео {video_info['id']} не подходит (не вертикальное или длинное), пропускаем")
            self.save_processed_video(video_info["id"])
            return False

        # Скачиваем
        video_file = self.download_video(video_info["url"])
        if not video_file:
            return False

        # Генерируем описание с рекламой
        description = self.generate_description(video_info["title"], video_info["url"])
        # Заголовок для клипа (можно взять оригинальный)
        title = video_info["title"][:200]

        # Загружаем в VK Клипы
        clip_url = self.upload_to_vk_clip(video_file, title, description)

        # Удаляем временный файл
        if os.path.exists(video_file):
            os.remove(video_file)

        if clip_url:
            self.save_processed_video(video_info["id"])
            logging.info(f"✅ Shorts опубликован как VK Клип: {clip_url}")
            return True
        else:
            logging.error(f"❌ Не удалось опубликовать {video_info['id']}")
            return False

    def run(self):
        logging.info("🚀 Бот запущен. Мониторинг YouTube Shorts -> VK Клипы")
        logging.info(f"Отслеживаемые каналы: {', '.join(self.channel_ids)}")
        while True:
            try:
                for channel_id in self.channel_ids:
                    logging.info(f"Проверка канала {channel_id}...")
                    latest = self.get_latest_video_from_channel(channel_id)
                    if latest and latest["id"] not in self.processed_videos:
                        self.process_short(channel_id, latest)
                    else:
                        logging.info(f"Новых видео на канале {channel_id} нет")
                logging.info(f"Ожидание {self.check_interval} секунд...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logging.info("Бот остановлен")
                break
            except Exception as e:
                logging.error(f"Неожиданная ошибка: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = YouTubeShortsToVKClipsBot()
    bot.run()
