#!/usr/bin/env python3
import os
import sys
import time
import logging
import requests
import feedparser
import yt_dlp
import vk_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VKReposter:
    def __init__(self):
        self.token = os.getenv("VK_TOKEN")
        self.group_id = os.getenv("VK_GROUP_ID")
        self.channels = [ch.strip() for ch in os.getenv("CHANNEL_IDS", "").split(",") if ch]
        self.ad = os.getenv("AD_TEXT", "Заработок на партнёрках → https://vk.me/1onesis")
        self.interval = int(os.getenv("CHECK_INTERVAL", "600"))
        
        logging.info(f"VK_TOKEN = {self.token[:10]}... (длина {len(self.token) if self.token else 0})")
        logging.info(f"VK_GROUP_ID = {self.group_id}")
        logging.info(f"CHANNEL_IDS = {self.channels}")
        
        if not self.token:
            raise ValueError("VK_TOKEN не задан")
        if not self.group_id:
            raise ValueError("VK_GROUP_ID не задан")
        
        # Инициализация VK API
        self.vk_session = vk_api.VkApi(token=self.token)
        self.vk = self.vk_session.get_api()
        
        self.processed = self.load_processed()
        logging.info("Инициализация завершена")

    def load_processed(self):
        if os.path.exists("processed.txt"):
            with open("processed.txt") as f:
                return set(line.strip() for line in f)
        return set()

    def save_processed(self, vid):
        with open("processed.txt", "a") as f:
            f.write(f"{vid}\n")
        self.processed.add(vid)

    def get_latest(self, channel_id):
        try:
            feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
            if feed.entries:
                e = feed.entries[0]
                return {"id": e.id.split(":")[-1], "url": e.link, "title": e.title}
        except Exception as e:
            logging.error(f"RSS error: {e}")
        return None

    def check_vertical(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info.get('duration', 0) > 60:
                    return False
                w, h = info.get('width'), info.get('height')
                if w and h:
                    return h > w
                for f in info.get('formats', []):
                    if f.get('width') and f.get('height'):
                        return f['height'] > f['width']
        except:
            pass
        return False

    def download(self, url, path="temp.mp4"):
        opts = {
            'outtmpl': path,
            'format': 'worst[ext=mp4]',
            'quiet': True,
            'socket_timeout': 60,
            'retries': 5,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return path
        except Exception as e:
            logging.error(f"Download failed: {e}")
            return None

    def upload_to_vk(self, video_path, desc):
        try:
            video_save = self.vk.video.save(
                name=os.path.basename(video_path),
                description=desc,
                group_id=int(self.group_id),
                is_private=0,
                wallpost=1
            )
            upload_url = video_save['upload_url']
            with open(video_path, 'rb') as f:
                files = {'video_file': f}
                resp = requests.post(upload_url, files=files)
            if resp.status_code == 200:
                logging.info("Video uploaded to VK")
                return True
            else:
                logging.error(f"Upload HTTP error: {resp.status_code}")
                return False
        except Exception as e:
            logging.error(f"VK API error: {e}")
            return False

    def process(self, video):
        logging.info(f"New video: {video['title']} ({video['id']})")
        if not self.check_vertical(video['url']):
            logging.info("Not vertical or >60s, skip")
            self.save_processed(video['id'])
            return
        path = self.download(video['url'])
        if not path:
            return
        desc = f"😂 {video['title']}\n\n#юмор #shorts\n\n{self.ad}"
        ok = self.upload_to_vk(path, desc)
        os.remove(path)
        if ok:
            self.save_processed(video['id'])
            logging.info("Published successfully")
        else:
            logging.error("Publication failed")

    def run(self):
        logging.info("Bot started, entering main loop")
        while True:
            for ch in self.channels:
                vid = self.get_latest(ch)
                if vid and vid['id'] not in self.processed:
                    self.process(vid)
            time.sleep(self.interval)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--test-url":
        test_url = sys.argv[2]
        logging.info(f"TEST MODE: {test_url}")
        bot = VKReposter()
        if bot.check_vertical(test_url):
            logging.info("Video is vertical, downloading...")
            path = bot.download(test_url)
            if path:
                desc = f"😂 Test video\n\n#юмор #shorts\n\n{bot.ad}"
                bot.upload_to_vk(path, desc)
                os.remove(path)
                logging.info("Test finished")
            else:
                logging.error("Download failed")
        else:
            logging.info("Video is not vertical or too long")
        sys.exit(0)
    bot = VKReposter()
    bot.run()
