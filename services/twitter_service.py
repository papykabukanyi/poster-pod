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

class TwitterService:
    def __init__(self):
        try:
            # Initialize V2 client
            self.client = tweepy.Client(
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
                wait_on_rate_limit=True
            )
            
            # Initialize Gemini
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel('gemini-pro')
                logging.info("Gemini AI initialized successfully")
            except Exception as e:
                logging.warning(f"Gemini init error: {e}")
                self.model = None

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
            
            # Initialize tracking attributes
            self.last_post_time = None
            self.last_trending_engagement = None
            self.post_interval = 1800  # 30 minutes
            self.trending_interval = 900  # 15 minutes
            self.retry_count = 0
            self.max_retries = 3
            
            self._add_activity_log('init', 'Twitter service initialized successfully')
            logging.info("Twitter service initialized successfully")
            
        except Exception as e:
            logging.error(f"Twitter init error: {e}")
            self.client = None
            self.v1_api = None
            self.model = None

    def check_connection(self):
        """Check if Twitter connection is working"""
        try:
            if not self.client or not self.v1_api:
                return False
                
            # Test v2 API connection
            me = self.client.get_me()
            if not me.data:
                return False
                
            # Test v1 API connection
            self.v1_api.verify_credentials()
            
            return True
            
        except tweepy.TooManyRequests:
            logging.warning("Rate limit hit during connection check")
            return True  # Consider it connected even if rate limited
            
        except Exception as e:
            logging.error(f"Connection check failed: {e}")
            self._add_activity_log('error', f"Connection check failed: {str(e)}")
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
        """Handle rate limiting with exponential backoff"""
        try:
            reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
            wait_time = max(reset_time - time.time(), 0)
            wait_time = min(wait_time, self.post_interval)
            
            if wait_time > 0:
                logging.warning(f"Rate limit hit, waiting {wait_time} seconds")
                self._add_activity_log('rate_limit', f"Waiting {wait_time}s")
                time.sleep(wait_time)
                
        except Exception as e:
            logging.error(f"Rate limit handling error: {e}")
            time.sleep(60)  # Default wait

    def post_article(self, article):
        """Post article to Twitter with image"""
        try:
            if not self.client or not self.v1_api:
                return False

            current_time = datetime.utcnow()
            
            if self.last_post_time:
                time_since_last = (current_time - self.last_post_time).total_seconds()
                if time_since_last < self.post_interval:
                    return False

            text = self._generate_tweet_text(article)
            media_id = None

            # Handle image if available
            if article.image_url and os.path.exists(article.image_url.lstrip('/')):
                try:
                    # Add watermark
                    watermarked_path = ImageService.add_watermark(
                        article.image_url.lstrip('/'),
                        "www.onposter.site/news"
                    )
                    if watermarked_path:
                        media = self.v1_api.media_upload(watermarked_path)
                        media_id = media.media_id
                        try:
                            os.remove(watermarked_path)
                        except:
                            pass
                except Exception as e:
                    logging.error(f"Media upload error: {e}")

            # Post tweet with retries
            for attempt in range(self.max_retries):
                try:
                    if media_id:
                        response = self.client.create_tweet(
                            text=text,
                            media_ids=[media_id]
                        )
                    else:
                        response = self.client.create_tweet(text=text)
                        
                    if response.data:
                        self.last_post_time = current_time
                        self.retry_count = 0
                        self._add_activity_log('post', f"Posted: {text[:50]}...")
                        return True
                        
                except tweepy.TooManyRequests as e:
                    self._handle_rate_limit(e)
                    continue
                    
                except Exception as e:
                    logging.error(f"Tweet error: {e}")
                    time.sleep(2 ** attempt)
                    continue

            return False

        except Exception as e:
            logging.error(f"Twitter post error: {e}")
            self._add_activity_log('error', f"Post error: {str(e)}")
            return False

    def _generate_tweet_text(self, article):
        """Generate tweet text using Gemini AI with fallback"""
        try:
            if self.model:
                prompt = f"""
                Create a compelling tweet (max 280 chars) about this news:
                Title: {article.title}
                Description: {article.description}
                include popular hashtags 2 or 3 of them
                Include the URL: www.onposter.site/news
                Make it engaging but professional.
                """
                
                response = self.model.generate_content(prompt)
                if response and response.text:
                    tweet = response.text.strip()
                    # Ensure URL is included
                    if "www.onposter.site/news" not in tweet:
                        tweet = f"{tweet[:230]}... www.onposter.site/news"
                    return tweet[:280]
                    
            # Fallback to basic generation
            return f"{article.title[:100]}...\n\nRead more: www.onposter.site/news"
            
        except Exception as e:
            logging.error(f"AI text generation error: {e}")
            return "Breaking news update at www.onposter.site/news"

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