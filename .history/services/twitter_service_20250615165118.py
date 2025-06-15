# services/twitter_service.py
from models.base import db_session
import tweepy
import logging
from datetime import datetime, timedelta
import os
import time
from config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    TWITTER_CLIENT_ID
)
from services.image_service import ImageService
from models.activity_log import ActivityLog
import google.generativeai as genai
from config import GEMINI_API_KEY
import concurrent
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import asyncio
from functools import partial

class TwitterService:
    def __init__(self):
        try:
            # Force Twitter API keys to be present
            if not TWITTER_API_KEY or not TWITTER_API_SECRET or not TWITTER_ACCESS_TOKEN or not TWITTER_ACCESS_SECRET:
                logging.error("Twitter API credentials missing - check environment variables")
                raise ValueError("Missing Twitter API credentials")

            # Initialize V2 client
            self.client = tweepy.Client(
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
                wait_on_rate_limit=True  # Changed to True to handle rate limits automatically
            )
            
            # Initialize V1 API for media uploads
            self.v1_auth = tweepy.OAuthHandler(
                TWITTER_API_KEY, 
                TWITTER_API_SECRET
            )
            self.v1_auth.set_access_token(
                TWITTER_ACCESS_TOKEN, 
                TWITTER_ACCESS_SECRET
            )
            self.v1_api = tweepy.API(self.v1_auth)
            
            # Initialize Gemini AI
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-pro')
                logging.info("Gemini AI initialized successfully")
            except Exception as e:
                logging.warning(f"Gemini init error: {e}")
                self.model = None
            
            # Initialize other attributes
            self.last_post_time = None
            self.post_interval = 1800  # 30 minutes
            self.retry_count = 0
            self.max_retries = 5  # Increased from 3 to 5 for more reliability
            self.api_timeout = 10  # Increased from 5 to 10 seconds for API calls
            self.post_timeout = 15  # Increased from 10 to 15 seconds for posts
            
            # Connection status cache
            self._connection_status = {
                'is_connected': False,
                'last_check': None,
                'cache_ttl': 300  # 5 minutes
            }
            
            # Initialize connection on startup
            self._update_connection_status()
            
            # Initialize executor with cleanup
            self.executor = ThreadPoolExecutor(max_workers=2)
            
            self._add_activity_log('init', 'Twitter service initialized successfully')
            logging.info("Twitter service initialized successfully")
            
        except Exception as e:
            logging.error(f"Twitter init error: {e}")
            self.client = None
            self.v1_api = None
            self.model = None

    def _update_connection_status(self):
        """Update cached connection status"""
        try:
            if not self.client:
                self._connection_status['is_connected'] = False
                return

            try:
                me = self.client.get_me()
                self._connection_status['is_connected'] = bool(me.data)
            except tweepy.TooManyRequests:
                self._connection_status['is_connected'] = True  # Consider connected if rate limited
            except Exception as e:
                logging.error(f"Connection update failed: {e}")
                self._connection_status['is_connected'] = False
                
            self._connection_status['last_check'] = datetime.utcnow()
            
        except Exception as e:
            logging.error(f"Status update error: {e}")
            self._connection_status['is_connected'] = False

    def check_connection(self):
        """Non-blocking connection check using cache"""
        try:
            current_time = datetime.utcnow()
            last_check = self._connection_status['last_check']
            
            # Update if cache expired
            if not last_check or (current_time - last_check).total_seconds() >= self._connection_status['cache_ttl']:
                self._update_connection_status()
                
            return self._connection_status['is_connected']
            
        except Exception as e:
            logging.error(f"Connection check error: {e}")
            return False

    def _add_activity_log(self, activity_type, message):
        """Add activity log to database with retry"""
        for attempt in range(3):
            try:
                with db_session() as session:
                    log = ActivityLog(
                        type=activity_type,
                        message=message,
                        timestamp=datetime.utcnow()
                    )
                    session.add(log)
                    session.commit()
                    break
            except Exception as e:
                logging.error(f"Activity log error (attempt {attempt+1}): {e}")
                if attempt == 2:  # Last attempt
                    logging.error("Failed to log activity after 3 attempts")
                time.sleep(1)  # Brief pause between retries

    def _update_rate_limits(self, response):
        """Update rate limit tracking from response headers"""
        try:
            if hasattr(response, 'response') and response.response:
                headers = response.response.headers
                self.remaining_calls = int(headers.get('x-rate-limit-remaining', 0))
                reset_time = int(headers.get('x-rate-limit-reset', 0))
                self.rate_limit_reset = datetime.fromtimestamp(reset_time)
        except Exception as e:
            logging.error(f"Rate limit update error: {e}")

    def _handle_rate_limit(self, e):
        """Non-blocking rate limit handler"""
        try:
            reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
            wait_time = max(reset_time - time.time(), 0)
            wait_time = min(wait_time, self.post_interval)
            
            if wait_time > 0:
                logging.warning(f"Rate limit hit, scheduling retry in {wait_time}s")
                self._add_activity_log('rate_limit', f"Retry scheduled in {wait_time}s")
                return wait_time
            return 0
            
        except Exception as e:
            logging.error(f"Rate limit handling error: {e}")
            return 60  # Default wait

    def post_article(self, article):
        """Post article with adjusted timeouts"""
        try:
            if not self.client or not self.v1_api:
                return False

            current_time = datetime.utcnow()
            
            if self.last_post_time:
                time_since_last = (current_time - self.last_post_time).total_seconds()
                if time_since_last < self.post_interval:
                    return False

            text = self._generate_tweet_text(article)
            
            # Use longer timeout for posting
            future = self.executor.submit(
                partial(self._post_with_retries, text=text, article=article)
            )
            
            try:
                result = future.result(timeout=self.post_timeout)
                if result:
                    self.last_post_time = current_time
                    return True
            except concurrent.futures.TimeoutError:
                logging.error("Post timed out")
                self._add_activity_log('error', "Post timed out")
                return False

            return False        except Exception as e:
            logging.error(f"Twitter post error: {e}")
            self._add_activity_log('error', f"Post error: {str(e)}")
            return False
              def _post_with_retries(self, text, article):
        """Handle posting with retries in background - text only, no media"""
        # Removed media_id handling - we only want text tweets

        # Post with retries
        for attempt in range(self.max_retries):
            try:
                # Always post text-only tweets
                response = self.client.create_tweet(text=text)
                    
                if response.data:
                    self._add_activity_log('post', f"Posted: {text[:50]}...")
                    return True
                    
            except tweepy.TooManyRequests as e:
                wait_time = self._handle_rate_limit(e)
                if wait_time:
                    time.sleep(min(wait_time, 5))  # Limited sleep time
                continue
                
            except Exception as e:
                logging.error(f"Tweet error: {e}")
                time.sleep(min(2 ** attempt, 5))  # Limited exponential backoff
                continue

        return False
        
    def _generate_tweet_text(self, article):
        """Generate tweet text using Gemini AI with fallback - ensure URL on new line to prevent auto-thumbnails"""
        try:
            if hasattr(self, 'model') and self.model:
                prompt = f"""
                Create a compelling tweet (max 250 chars) about this news:
                Title: {article.title}
                Description: {article.description}
                Include 1-2 relevant hashtags
                DO NOT include the URL - it will be added separately.
                Make it engaging but professional.
                """
                
                response = self.model.generate_content(prompt)
                if response and hasattr(response, 'text'):
                    tweet_text = response.text.strip()
                    # Make sure the URL is on a new line at the end
                    return f"{tweet_text[:250]}\n\nwww.onposter.site/news"
            
            # Fallback to basic generation
            hashtags = "#BreakingNews #News"
            base_text = f"{article.title[:150]}..."
            return f"{base_text}\n{hashtags}\n\nwww.onposter.site/news"
        except Exception as e:
            logging.error(f"AI text generation error: {e}")
            return f"Breaking News: {article.title[:180]}...\n#News\n\nwww.onposter.site/news"

    def get_recent_logs(self, limit=10):
        """Get recent activity logs with retry"""
        for attempt in range(3):
            try:
                with db_session() as session:
                    logs = session.query(ActivityLog)\
                        .order_by(ActivityLog.timestamp.desc())\
                        .limit(limit)\
                        .all()
                    return [log.to_dict() for log in logs]
            except Exception as e:
                logging.error(f"Log fetch error (attempt {attempt+1}): {e}")
                time.sleep(1)
        return []  # Return empty list if all retries fail

    def __del__(self):
        """Cleanup on deletion"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)
        except Exception as e:
            logging.error(f"Cleanup error: {e}")