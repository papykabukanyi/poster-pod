# services/scheduler_service.py
import threading
import time
import os
import logging
from datetime import datetime, timedelta
from services.news_service import NewsService
from services.image_service import ImageService
from services.twitter_service import TwitterService  # Add this import

class SchedulerService:
    def __init__(self):
        self.news_interval = 7200  # 2 hours
        self.twitter_interval = 1800  # 30 minutes
        self.cleanup_interval = 43200  # 12 hours
        self.running = False
        self.thread = None
        self.twitter_service = TwitterService()
        self.last_news_update = datetime.utcnow()
        self.last_twitter_update = datetime.utcnow()
        self.last_cleanup = datetime.utcnow()
        self.logger = logging.getLogger(__name__)

    @property
    def next_news_update(self):
        return self.last_news_update + timedelta(seconds=self.news_interval)

    @property
    def next_twitter_update(self):
        return self.last_twitter_update + timedelta(seconds=self.twitter_interval)

    def cleanup_images(self):
        """Delete cached images older than 2 hours"""
        try:
            now = datetime.now()
            image_dir = "static/images/generated"
            count = 0

            if os.path.exists(image_dir):
                for filename in os.listdir(image_dir):
                    filepath = os.path.join(image_dir, filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if now - file_modified > timedelta(hours=2):
                        os.remove(filepath)
                        count += 1

            self.logger.info(f"Cleaned up {count} old images")
        except Exception as e:
            self.logger.error(f"Error during image cleanup: {e}")

    def run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = datetime.utcnow()

                # News update (every 2 hours)
                if current_time >= self.next_news_update:
                    self.logger.info("Running scheduled news update")
                    if NewsService.fetch_news(force_breaking=True):
                        self.last_news_update = current_time
                        self.logger.info(f"News updated at {current_time}")

                # Twitter post (every 30 minutes)
                if current_time >= self.next_twitter_update:
                    cached_news = NewsService.get_cached_news()
                    if cached_news and cached_news.get('breaking'):
                        if self.twitter_service.post_article(cached_news['breaking']):
                            self.last_twitter_update = current_time
                            self.logger.info(f"Twitter post at {current_time}")

                # Cleanup (every 12 hours)
                if (current_time - self.last_cleanup).total_seconds() >= self.cleanup_interval:
                    self.cleanup_images()
                    self.last_cleanup = current_time

                time.sleep(30)

            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(60)

    def start(self):
        """Start the scheduler"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
            self.thread.start()
            self.logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
            self.logger.info("Scheduler stopped")