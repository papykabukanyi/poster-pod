# services/scheduler_service.py
import threading
import time
import os
import base64
import uuid
import logging
from datetime import datetime, timedelta
import tweepy
from services.image_service import ImageService

class SchedulerService:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.news_interval = 3600  # 1 hour for news updates
        self.twitter_interval = 1800  # 30 minutes for tweets
        self.cleanup_interval = 43200  # 12 hours for cleanup
        self.running = False
        self.thread = None
        
        # Import services here to avoid circular imports
        from services.twitter_service import TwitterService
        from services.news_service import NewsService
        
        self.twitter_service = TwitterService()
        self.news_service = NewsService()
        
        # Initialize timestamps as None to force initial updates
        self.last_news_update = None
        self.last_twitter_update = datetime.utcnow() - timedelta(minutes=30)  # Make first update happen quickly
        self.last_cleanup = datetime.utcnow()
        
        self._next_news_update = None
        self._next_twitter_update = self.last_twitter_update + timedelta(seconds=self.twitter_interval)
        
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Initial fetch of news and Twitter post"""
        try:
            # Import here to avoid circular imports
            from services.news_service import NewsService
            
            # Initial news fetch
            if NewsService.fetch_news(force_breaking=True):
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
            return None    def run_scheduler(self):
        """Main scheduler loop"""
        self.initialize()  # Perform initial updates
        
        from services.news_service import NewsService
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                self.logger.info(f"Scheduler running at {current_time}")

                # News update (every 1 hour now)
                try:
                    if not self.last_news_update or current_time >= self.next_news_update:
                        self.logger.info("Running scheduled news update")
                        if NewsService.fetch_news(force_breaking=True):
                            self.last_news_update = current_time
                            self._next_news_update = current_time + timedelta(seconds=self.news_interval)
                            self.logger.info(f"News updated at {current_time}, next update at {self._next_news_update}")
                        else:
                            self.logger.warning("News update failed, will retry in 15 minutes")
                            self._next_news_update = current_time + timedelta(minutes=15)
                except Exception as e:
                    self.logger.error(f"News update error: {e}")
                    # Even if there's an error, schedule next attempt
                    self._next_news_update = current_time + timedelta(minutes=15)  # Retry in 15 minutes
                    self.logger.info(f"Rescheduled news update for {self._next_news_update}")

                # Twitter post (every 30 minutes)
                try:
                    if not self.last_twitter_update or current_time >= self.next_twitter_update:
                        self.logger.info("Time to post to Twitter")
                        
                        # First, verify Twitter connection
                        if not self.twitter_service.check_connection():
                            self.logger.warning("Twitter connection not available, rebuilding client")
                            # Recreate Twitter service to reset connection
                            from services.twitter_service import TwitterService
                            self.twitter_service = TwitterService()
                            if not self.twitter_service.check_connection():
                                self.logger.error("Twitter connection still unavailable after rebuild")
                                self._next_twitter_update = current_time + timedelta(minutes=15)
                                continue
                            
                        # Get latest news from database directly to ensure freshness
                        cached_news = NewsService.get_cached_news()
                        
                        if not cached_news:
                            self.logger.warning("No news available for Twitter post")
                            # Force a news refresh right now
                            if NewsService.fetch_news(force_breaking=True):
                                self.logger.info("Forced news refresh successful")
                                cached_news = NewsService.get_cached_news()
                            else:
                                self.logger.error("Forced news refresh failed")
                                self._next_twitter_update = current_time + timedelta(minutes=15)
                                continue
                                
                        if cached_news:
                            article = None
                            # Try to use breaking news first
                            if cached_news.get('breaking'):
                                article = cached_news['breaking']
                                self.logger.info(f"Using breaking news article: {article.title if hasattr(article, 'title') else 'Unknown'}")
                            # Fall back to other news if no breaking news
                            elif cached_news.get('other') and len(cached_news['other']) > 0:
                                article = cached_news['other'][0]
                                self.logger.info(f"Using regular news article: {article.title if hasattr(article, 'title') else 'Unknown'}")
                                
                            if article:
                                self.logger.info(f"Attempting Twitter post for article: {article.title if hasattr(article, 'title') else 'Unknown'}")
                                posting_result = self.twitter_service.post_article(article)
                                if posting_result:
                                    self.last_twitter_update = current_time
                                    self._next_twitter_update = current_time + timedelta(seconds=self.twitter_interval)
                                    self.logger.info(f"Twitter post successful at {current_time}, next post at {self._next_twitter_update}")
                                else:
                                    self.logger.warning("Twitter post failed, will retry in 15 minutes")
                                    self._next_twitter_update = current_time + timedelta(minutes=15)
                            else:
                                self.logger.warning("No article available after news refresh")
                                self._next_twitter_update = current_time + timedelta(minutes=15)
                        else:
                            self.logger.warning("Still no news available after refresh")
                            self._next_twitter_update = current_time + timedelta(minutes=15)
                            
                except tweepy.TooManyRequests as e:
                    retry_after = int(e.response.headers.get('x-rate-limit-reset', 900)) 
                    self.logger.warning(f"Twitter rate limit hit, waiting {retry_after} seconds")
                    self._next_twitter_update = current_time + timedelta(seconds=min(retry_after, 900))  # Cap at 15 minutes
                except Exception as e:
                    self.logger.error(f"Twitter post error: {str(e)}")
                    # Schedule retry after a short delay
                    self._next_twitter_update = current_time + timedelta(minutes=15)
                    self.logger.info(f"Rescheduled Twitter post for {self._next_twitter_update}")

                # Cleanup (every 12 hours)
                if (current_time - self.last_cleanup).total_seconds() >= self.cleanup_interval:
                    self.logger.info("Running scheduled image cleanup")
                    self.cleanup_images()
                    self.last_cleanup = current_time
                    self.logger.info(f"Cleanup completed at {current_time}")

                # Log next scheduled events
                self.logger.info(f"Next news update: {self._next_news_update}")
                self.logger.info(f"Next Twitter post: {self._next_twitter_update}")
                
                # Sleep for a shorter time and check more frequently
                time.sleep(30)

            except Exception as e:
                self.logger.error(f"Scheduler error: {str(e)}")
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