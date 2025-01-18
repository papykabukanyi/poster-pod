# services/scheduler_service.py
import threading
import time
import os
import base64
import uuid
import logging
from datetime import datetime, timedelta
from services.news_service import NewsService
from services.image_service import ImageService
from services.twitter_service import TwitterService  # Add this import

class SchedulerService:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.news_interval = 7200  # 2 hours in seconds (unchanged)
        self.twitter_interval = 1800  # 30 minutes in seconds
        self.cleanup_interval = 43200  # 12 hours (unchanged)
        self.running = False
        self.thread = None
        self.twitter_service = TwitterService()
        self.news_service = NewsService()
        
        # Initialize timestamps as None to force initial updates
        self.last_news_update = None
        self.last_twitter_update = datetime.utcnow()  # Initialize with current time
        self.last_cleanup = datetime.utcnow()
        
        self._next_news_update = None
        self._next_twitter_update = self.last_twitter_update + timedelta(seconds=self.twitter_interval)
        
        self.logger = logging.getLogger(__name__)

        # Add to existing init
        self.last_trending_update = None
        self.trending_interval = 900  # 15 minutes
        self._next_trending_update = None

    def initialize(self):
        """Initial fetch of news and Twitter post"""
        try:
            # Initial news fetch
            if NewsService.fetch_news(force_breaking=True):  # Using class method
                self.last_news_update = datetime.utcnow()
                self._next_news_update = self.last_news_update + timedelta(seconds=self.news_interval)
                self.logger.info(f"Initial news fetch successful. Next update in {self.news_interval/3600} hours")
                
                # Initial Twitter post
                cached_news = NewsService.get_cached_news()
                if cached_news and cached_news.get('breaking'):
                    if self.twitter_service.post_article(cached_news['breaking']):
                        self.last_twitter_update = datetime.utcnow()
                        self._next_twitter_update = self.last_twitter_update + timedelta(seconds=self.twitter_interval)
                        self.logger.info("Initial Twitter post successful")
        except Exception as e:
            self.logger.error(f"Initialization error: {e}")

    @property
    def next_twitter_update(self):
        """Get next Twitter update time"""
        current_time = datetime.utcnow()
        if not self._next_twitter_update or current_time >= self._next_twitter_update:
            self._next_twitter_update = current_time + timedelta(seconds=self.twitter_interval)
        return self._next_twitter_update

    @property
    def next_news_update(self):
        if not self._next_news_update:
            current_time = datetime.utcnow()
            self._next_news_update = current_time + timedelta(seconds=self.news_interval)
        return self._next_news_update

    @property
    def next_trending_update(self):
        """Get next trending engagement time"""
        current_time = datetime.utcnow()
        if not self._next_trending_update or current_time >= self._next_trending_update:
            self._next_trending_update = current_time + timedelta(seconds=self.trending_interval)
        return self._next_trending_update

    def get_next_update(self):
        return self.next_news_update

    def cleanup_images(self):
        """Delete cached images older than 12 hours"""
        try:
            now = datetime.utcnow()
            image_dir = "static/images/generated"
            count = 0

            if os.path.exists(image_dir):
                for filename in os.listdir(image_dir):
                    filepath = os.path.join(image_dir, filename)
                    try:
                        file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if now - file_modified > timedelta(hours=12):
                            os.remove(filepath)
                            count += 1
                    except (OSError, IOError) as e:
                        self.logger.error(f"Error processing file {filepath}: {e}")
                        continue

            self.logger.info(f"Cleaned up {count} old images")
            return count
        except Exception as e:
            self.logger.error(f"Error during image cleanup: {e}")
            return 0

    def handle_base64_image(self, base64_data):
        """Handle base64 encoded images"""
        try:
            if not base64_data.startswith('data:image'):
                return None
                
            # Extract actual base64 data
            image_data = base64_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            
            # Generate unique filename
            filename = f"generated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join("static/images/generated", filename)
            
            # Save image
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
                
            return filepath
        except Exception as e:
            self.logger.error(f"Error handling base64 image: {e}")
            return None

    def run_scheduler(self):
        """Main scheduler loop"""
        self.initialize()  # Perform initial updates
        
        while self.running:
            try:
                current_time = datetime.utcnow()

                # News update (every 2 hours)
                if not self.last_news_update or current_time >= self.next_news_update:
                    self.logger.info("Running scheduled news update")
                    if NewsService.fetch_news(force_breaking=True):  # Using class method
                        self.last_news_update = current_time
                        self._next_news_update = current_time + timedelta(seconds=self.news_interval)
                        self.logger.info(f"News updated at {current_time}")

                # Twitter post (every 30 minutes)
                if not self.last_twitter_update or current_time >= self.next_twitter_update:
                    cached_news = NewsService.get_cached_news()
                    if cached_news and cached_news.get('breaking'):
                        if self.twitter_service.post_article(cached_news['breaking']):
                            self.last_twitter_update = current_time
                            self._next_twitter_update = current_time + timedelta(seconds=self.twitter_interval)
                            self.logger.info(f"Twitter post at {current_time}")

                # Trending engagement check
                if not self.last_trending_update or current_time >= self.next_trending_update:
                    if self.twitter_service.engage_trending_accounts():
                        self.last_trending_update = current_time
                        self._next_trending_update = current_time + timedelta(seconds=self.trending_interval)
                        self.logger.info(f"Trending engagement at {current_time}")

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