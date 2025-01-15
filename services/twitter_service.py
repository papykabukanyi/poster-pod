# services/twitter_service.py
import tweepy
import logging
import google.generativeai as genai
from datetime import datetime, timedelta
from services.image_service import ImageService
from config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    GEMINI_API_KEY
)

class TwitterService:
    def __init__(self):
        try:
            # Initialize both v1 and v2 clients
            auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
            auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
            self.api = tweepy.API(auth)  # v1 API for media upload
            self.client = tweepy.Client(  # v2 API for tweets
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET
            )
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.last_post_time = None
            self.post_interval = 1800  # 30 minutes
            logging.info("Twitter service initialized successfully")
        except Exception as e:
            logging.error(f"Twitter initialization error: {e}")
            self.api = None
            self.client = None

    def _generate_caption(self, article):
        try:
            prompt = f"""Create an engaging tweet for this news article with trending hashtags:
            Title: {article.title}
            Description: {article.description}
            Rules:
            - Must be catchy and viral-worthy
            - Include relevant trending hashtags
            - Maximum 280 characters
            - End with 'More news: www.onposter.site/news | Best podcasts: www.onposter.site'"""
            
            response = self.model.generate_content(prompt)
            caption = response.text.strip()
            if len(caption) > 280:
                caption = caption[:250] + "... www.onposter.site/news"
            return caption
        except Exception as e:
            logging.error(f"Caption generation error: {e}")
            return self._get_fallback_caption(article)

    def _get_fallback_caption(self, article):
        base_caption = f"{article.title[:180]}..."
        return f"{base_caption}\nMore news: www.onposter.site/news | Best podcasts: www.onposter.site"

    def post_article(self, article):
        try:
            if not self.client or not self.api:
                logging.error("Twitter clients not initialized")
                return False

            current_time = datetime.utcnow()
            
            # Strict 30-minute check
            if self.last_post_time:
                time_since_last = (current_time - self.last_post_time).total_seconds()
                if time_since_last < 1800:  # 30 minutes in seconds
                    logging.info(f"Skipping Twitter post - only {time_since_last} seconds since last post")
                    return False

            # Get watermarked image
            if article.image_url:
                try:
                    image_path = article.image_url.lstrip('/')
                    watermarked_image = ImageService.add_watermark(image_path)
                    
                    # Upload media using v1 API
                    media = self.api.media_upload(filename=watermarked_image)
                    
                    # Create tweet with media using v2 API
                    caption = self._generate_caption(article)
                    response = self.client.create_tweet(
                        text=caption,
                        media_ids=[media.media_id]
                    )
                except Exception as e:
                    logging.error(f"Media upload error: {e}")
                    # Fallback to text-only tweet
                    caption = self._generate_caption(article)
                    response = self.client.create_tweet(text=caption)
            else:
                # Text-only tweet
                caption = self._generate_caption(article)
                response = self.client.create_tweet(text=caption)
            
            if hasattr(response, 'data') and response.data:
                self.last_post_time = current_time
                logging.info(f"Successfully posted to Twitter at {current_time}")
                return True
                
            return False

        except Exception as e:
            logging.error(f"Twitter post error: {e}")
            return False

    def check_connection(self):
        """Check if Twitter connection is working"""
        try:
            if not self.client:
                return False
            # Test API connection
            self.client.get_me()
            return True
        except Exception as e:
            logging.error(f"Twitter connection check failed: {e}")
            return False