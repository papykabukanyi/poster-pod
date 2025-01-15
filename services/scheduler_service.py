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
        self.news_interval = 7200  # 2 hours in seconds
        self.twitter_interval = 1800  # 30 minutes in seconds
        self.cleanup_interval = 9200  # 2 hours in seconds
        self.running = False
        self.thread = None
        self.twitter_service = TwitterService()  # Initialize Twitter service
        self.last_news_update = None
        self.last_twitter_update = None
        self.last_cleanup = None
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

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

                # News update check (every 2 hours)
                if not self.last_news_update or (current_time - self.last_news_update).total_seconds() >= self.news_interval:
                    self.logger.info("Running scheduled news update")
                    news_service = NewsService()
                    if news_service.fetch_news(force_breaking=True):
                        self.last_news_update = current_time
                        news_service.next_update_time = current_time + timedelta(seconds=self.news_interval)

                # Twitter post check (every 30 minutes)
                if not self.last_twitter_update or (current_time - self.last_twitter_update).total_seconds() >= self.twitter_interval:
                    cached_news = NewsService.get_cached_news()
                    if cached_news and cached_news.get('breaking'):
                        self.logger.info("Running scheduled Twitter post")
                        if self.twitter_service.post_article(cached_news['breaking']):
                            self.last_twitter_update = current_time

                # Cleanup check (every 2 hours)
                if not self.last_cleanup or (current_time - self.last_cleanup).total_seconds() >= self.cleanup_interval:
                    self.logger.info("Running scheduled image cleanup")
                    self.cleanup_images()
                    self.last_cleanup = current_time

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes on error

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