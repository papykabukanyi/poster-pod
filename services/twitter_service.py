# services/twitter_service.py
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
    GEMINI_API_KEY
)
import google.generativeai as genai

class TwitterService:
    def __init__(self):
        try:
            # Initialize both v1 and v2 clients
            self.v1_auth = tweepy.OAuthHandler(
                TWITTER_API_KEY, 
                TWITTER_API_SECRET
            )
            self.v1_auth.set_access_token(
                TWITTER_ACCESS_TOKEN, 
                TWITTER_ACCESS_SECRET
            )
            
            # V1 API for media upload
            self.v1_api = tweepy.API(self.v1_auth, wait_on_rate_limit=True)
            
            # V2 API for tweets
            self.client = tweepy.Client(
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
                wait_on_rate_limit=True
            )
            
            # Initialize AI for captions
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            
            self.last_post_time = None
            self.post_interval = 1800  # 30 minutes
            self.retry_count = 0
            self.max_retries = 3
            
            logging.info("Twitter service initialized successfully")
            
        except Exception as e:
            logging.error(f"Twitter initialization error: {e}")
            self.client = None
            self.v1_api = None

    def post_article(self, article):
        """Post article to Twitter using v2 API"""
        try:
            if not self.client or not self.v1_api:
                logging.error("Twitter API not initialized")
                return False

            current_time = datetime.utcnow()
            
            # Check posting interval
            if self.last_post_time:
                time_since_last = (current_time - self.last_post_time).total_seconds()
                if time_since_last < self.post_interval:
                    logging.info(f"Rate limit: Waiting {self.post_interval - time_since_last} seconds")
                    return False

            # Generate caption
            caption = self._generate_caption(article)
            
            # Upload media using v1 API
            media_id = None
            if article.image_url and os.path.exists(article.image_url.lstrip('/')):
                try:
                    media = self.v1_api.media_upload(article.image_url.lstrip('/'))
                    media_id = media.media_id
                except Exception as e:
                    logging.error(f"Media upload error: {e}")

            # Post tweet using v2 API
            try:
                if media_id:
                    response = self.client.create_tweet(
                        text=caption,
                        media_ids=[media_id]
                    )
                else:
                    response = self.client.create_tweet(
                        text=caption
                    )
                
                if response.data:
                    self.last_post_time = current_time
                    self.retry_count = 0
                    logging.info(f"Successfully posted to Twitter at {current_time}")
                    return True

            except tweepy.TweepyException as e:
                if "duplicate" in str(e).lower():
                    logging.warning("Duplicate tweet detected, modifying content")
                    caption = f"{caption} {current_time.strftime('%H:%M:%S')}"
                    return self.post_article(article)  # Retry with modified caption
                    
                if self.retry_count < self.max_retries:
                    self.retry_count += 1
                    time.sleep(2 ** self.retry_count)  # Exponential backoff
                    return self.post_article(article)
                    
                logging.error(f"Twitter post error after {self.max_retries} retries: {e}")
                return False

        except Exception as e:
            logging.error(f"Twitter post error: {e}")
            return False

    def _generate_caption(self, article):
        try:
            prompt = f"""Create an engaging tweet for this news article:
            Title: {article.title}
            Description: {article.description}
            Rules:
            - Must be catchy and viral-worthy
            - Include 2-3 relevant hashtags
            - Maximum 250 characters (leave room for URL)
            - End with 'More at www.onposter.site/news'"""
            
            response = self.model.generate_content(prompt)
            caption = response.text.strip()
            
            if len(caption) > 250:
                caption = self._get_fallback_caption(article)
            
            return caption
            
        except Exception as e:
            logging.error(f"Caption generation error: {e}")
            return self._get_fallback_caption(article)

    def _get_fallback_caption(self, article):
        title = article.title[:180] if article.title else "Breaking News"
        return f"{title}... More at www.onposter.site/news #News #BreakingNews"

    def check_connection(self):
        """Check if Twitter connection is working"""
        try:
            if not self.client or not self.v1_api:
                return False
                
            # Test v1 credentials
            self.v1_api.verify_credentials()
            
            # Test v2 credentials
            self.client.get_me()
            
            return True
            
        except Exception as e:
            logging.error(f"Twitter connection check failed: {e}")
            return False