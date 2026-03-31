#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import gc
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
        self.max_duration = int(os.getenv("MAX_DURATION_SECONDS", 60))

        if not self.channel_ids:
            logging.error("Не указаны CHANNEL_IDS в .env. Бот остановлен.")
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

    def is_vertical_video(self, url):
        """Проверяет вертикальность и длительность (без скачивания)"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get('duration', 0)
                if duration > self.max_duration:
                    logging.info(f"Видео слишком длинное: {duration} сек (макс {self.max_duration})")
                    return False

                width = info.get('width')
                height = info.get('height')
                if width and height:
                    return height > width
                formats = info.get('formats', [])
                for f in formats:
                    if f.get('width') and f.get('height'):
                        return f['height'] > f['width']
                logging.warning(f"Не удалось определить размеры видео {url}, пропускаем")
                return False
        except Exception as e:
            logging.error(f"Ошибка проверки ориентации/длительности: {e}")
            return False

    def download_video(self, url, output_path="temp_video.mp4"):
        """Скачивает видео с ограничением высоты 480p, без FFmpeg"""
        try:
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
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
        prompt = f"""
        Напиши короткое и привлекательное описание для смешного вертикального видео (YouTube Shorts), которое будет опубликовано в VK.
        Оригинальное название видео: "{video_title}"
        Ссылка на видео: {video_url}
        
        Требования:
        - Язык: русский
        - Длина: 2-3 предложения
        - Добавь 3-5 хэштегов (#юмор #shorts и т.п.)
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
                ai_text = response.choices[0].message.content
                if ai_text is None:
                    raise ValueError("AI вернул None")
                ai_text = ai_text.strip()
                full_description = f"{ai_text}\n\n{self.ad_text}"
                return full_description
            except RateLimitError:
                wait = 20 * (attempt + 1)
                logging.warning(f"Превышен лимит OpenRouter. Ждём {wait} сек...")
                time.sleep(wait)
            except Exception as e:
                logging.error(f"Ошибка AI: {e}")
                if attempt == max_retries - 1:
                    fallback = f"😄 Смешное вертикальное видео: {video_title}\n\n#юмор #shorts\n\n{self.ad_text}"
                    return fallback
        return f"Смешное видео: {video_title}\n\n{self.ad_text}"

    def post_to_vk(self, video_path, description):
        """Публикует видео на стену сообщества (без is_clip)"""
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
        logging.info(f"Новое видео на канале {channel_id}: {video_info['title']} ({video_info['url']})")

        if not self.is_vertical_video(video_info["url"]):
            logging.info(f"Видео {video_info['id']} не вертикальное или слишком длинное. Пропускаем.")
            self.save_processed_video(video_info["id"])
            return False

        video_file = self.download_video(video_info["url"])
        if not video_file:
            return False

        gc.collect()
        time.sleep(1)

        description = self.generate_description(video_info["title"], video_info["url"])
        success = self.post_to_vk(video_file, description)

        if os.path.exists(video_file):
            os.remove(video_file)

        gc.collect()

        if success:
            self.save_processed_video(video_info["id"])
            logging.info(f"Вертикальное видео {video_info['id']} успешно опубликовано")
        else:
            logging.error(f"Не удалось опубликовать видео {video_info['id']}")
        return success

    def run(self):
        logging.info("🚀 Бот запущен. Мониторинг каналов (только вертикальные клипы до {} сек): {}".format(
            self.max_duration, ", ".join(self.channel_ids)))
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
    if len(sys.argv) >= 3 and sys.argv[1] == "--test-url":
        test_url = sys.argv[2]
        logging.info(f"🧪 ТЕСТОВЫЙ РЕЖИМ: обработка видео {test_url}")
        bot = VKYouTubeReposter()
        if bot.is_vertical_video(test_url):
            logging.info("Видео подходит (вертикальное, короткое). Скачиваем...")
            video_file = bot.download_video(test_url)
            if video_file:
                description = bot.generate_description("Тестовое видео из Shorts", test_url)
                bot.post_to_vk(video_file, description)
                os.remove(video_file)
                gc.collect()
                logging.info("✅ Тестовая публикация завершена")
            else:
                logging.error("❌ Не удалось скачать видео")
        else:
            logging.info("❌ Видео не вертикальное или слишком длинное. Тест прерван.")
        sys.exit(0)

    bot = VKYouTubeReposter()
    bot.run()
