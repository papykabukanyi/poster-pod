import os
import requests
import threading
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from models.news import NewsArticle
from models.base import db_session
from config import NEWSDATA_API_KEY
from services.image_service import ImageService
import hashlib
from services.linkedin_service import LinkedInService
import logging
from services.twitter_service import TwitterService

class NewsService:
    _instance = None
    _cache = {
        'articles': None,
        'last_fetch': None,
        'next_update': None,
        'breaking': None,
        'other': []
    }
    seen_articles = set()  # Track seen articles

    def __init__(self):
        self.last_update_time = None
        self.next_update_time = None
        self.breaking_news_check_interval = 7200  # 2 hours
        self.twitter_interval = 1800  # 30 minutes
        self.last_twitter_post = None
        self.last_linkedin_post = None
        self.linkedin_post_interval = 7200  # 2 hours

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def fetch_news(self, force_breaking=False):
        try:
            current_time = datetime.utcnow()
            
            # Check cache validity
            if not force_breaking and self._cache['last_fetch']:
                time_since_cache = (current_time - self._cache['last_fetch']).total_seconds()
                if time_since_cache < self.breaking_news_check_interval:
                    logging.info("Using cached news articles")
                    return True

            # Update timing
            self.last_update_time = current_time
            self.next_update_time = current_time + timedelta(seconds=self.breaking_news_check_interval)
            
            # Clear image cache
            ImageService.clear_used_images()
            
            # Fetch from API
            params = {
                'apikey': NEWSDATA_API_KEY,
                'country': 'us,gb',
                'language': 'en',
                'category': 'top',
                'size': 10
            }
            
            response = requests.get('https://newsdata.io/api/1/news', params=params)
            
            if response.status_code == 200:
                articles = response.json().get('results', [])
                
                if articles:
                    with db_session() as session:
                        # Clear old articles
                        session.query(NewsArticle).delete()
                        
                        # Process breaking news
                        breaking_news = self._process_article(articles[0], is_breaking=True)
                        if breaking_news:
                            session.add(breaking_news)
                        
                        # Process other news
                        other_news = []
                        seen_titles = {articles[0]['title']}
                        
                        for article in articles[1:4]:  # Limit to 3 other articles
                            if article['title'] not in seen_titles:
                                seen_titles.add(article['title'])
                                news_article = self._process_article(article)
                                if news_article:
                                    other_news.append(news_article)
                        
                        session.add_all(other_news)
                        session.commit()
                        
                        # Update cache
                        self._cache.update({
                            'breaking': breaking_news,
                            'other': other_news,
                            'last_fetch': current_time,
                            'next_update': self.next_update_time
                        })
                        
                        logging.info(f"Updated news at {current_time} with {len(other_news) + 1} articles")
                        return True
            
            return False

        except Exception as e:
            logging.error(f"Error fetching news: {e}")
            return False

    @classmethod
    def _process_article(cls, article_data, is_breaking=False):
        try:
            # Create hash for deduplication
            article_hash = hashlib.md5(
                f"{article_data['title']}{article_data['description']}".encode()
            ).hexdigest()
            
            # Skip if already seen
            if article_hash in cls.seen_articles:
                return None
                
            cls.seen_articles.add(article_hash)
            
            # Generate image path
            image_path = f"static/images/generated/{article_hash}.jpg"
            final_image_path = None
            
            # Handle image
            if article_data.get('image_url'):
                final_image_path = ImageService.get_cached_image(
                    article_data['image_url'],
                    image_path
                )
            
            if not final_image_path:
                final_image_path = ImageService.generate_news_image(
                    article_data['title'],
                    article_data['link'],
                    image_path
                )
            
            # Create article
            return NewsArticle(
                title=article_data['title'],
                description=article_data['description'],
                url=article_data['link'],
                image_url=f"/{image_path}" if final_image_path else None,
                published_at=datetime.fromisoformat(article_data['pubDate'].replace('Z', '+00:00')),
                source=article_data['source_id'],
                category='breaking' if is_breaking else 'news',
                is_breaking=is_breaking
            )

        except Exception as e:
            logging.error(f"Error processing article: {e}")
            return None

    @classmethod
    def start_scheduler(cls):
        def run_scheduler():
            print("Starting news scheduler...")
            while True:
                try:
                    # Check for new news
                    cls.get_instance().fetch_news()
                    time.sleep(cls.get_instance().breaking_news_check_interval)
                    
                except Exception as e:
                    print(f"Scheduler error: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        print("News scheduler started")

    @classmethod
    def force_refresh(cls):
        """Force an immediate refresh of news"""
        current_time = datetime.utcnow()
        # Only reset next_update_time if successful
        if cls.get_instance().fetch_news(force_breaking=True):
            cls.get_instance().last_update_time = current_time
            cls.get_instance().next_update_time = current_time + timedelta(seconds=cls.get_instance().breaking_news_check_interval)

    @classmethod
    def get_cached_news(cls):
        instance = cls.get_instance()
        try:
            current_time = datetime.utcnow()
            
            # Return cache if valid
            if cls._cache['articles'] and cls._cache.get('next_update'):
                if current_time < cls._cache['next_update']:
                    return cls._cache['articles']
            
            # Get from database
            with db_session() as session:
                breaking_news = session.query(NewsArticle).filter_by(is_breaking=True)\
                                    .order_by(NewsArticle.published_at.desc())\
                                    .first()
                other_news = session.query(NewsArticle).filter_by(is_breaking=False)\
                                  .order_by(NewsArticle.published_at.desc())\
                                  .limit(3)\
                                  .all()
                
                articles = {
                    'breaking': breaking_news,
                    'other': other_news,
                    'total': len(other_news) + (1 if breaking_news else 0)
                }
                
                # Update cache
                cls._cache['articles'] = articles
                cls._cache['last_fetch'] = current_time
                cls._cache['next_update'] = current_time + timedelta(seconds=instance.breaking_news_check_interval)
                
                return articles
                
        except Exception as e:
            logging.error(f"Error getting cached news: {e}")
            return {'breaking': None, 'other': [], 'total': 0}

    @classmethod
    def get_next_update_time(cls):
        instance = cls.get_instance()
        current_time = datetime.utcnow()
        if not instance.next_update_time:
            instance.next_update_time = current_time + timedelta(seconds=instance.breaking_news_check_interval)
        return instance.next_update_time