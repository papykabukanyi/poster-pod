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
import logging

# Import Twitter service at the end to avoid circular imports
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
        self.breaking_news_check_interval = 3600  # Reduced from 7200 (2 hours) to 3600 (1 hour) for more frequent updates
        self.twitter_interval = 1800  # 30 minutes
        self.last_twitter_post = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance    @classmethod
    def fetch_news(cls, force_breaking=False):
        """Class method for fetching news"""
        try:
            current_time = datetime.utcnow()
            
            # Check cache validity - but with forced refresh, always fetch
            if not force_breaking and cls._cache['last_fetch']:
                time_since_cache = (current_time - cls._cache['last_fetch']).total_seconds()
                if time_since_cache < 1800:  # Reduced to 30 minutes for more frequent updates
                    logging.info("Using cached news")
                    return True

            # Always clear cache when fetching new news
            cls._cache['articles'] = None
            
            # Set no-cache headers to avoid stale API responses
            headers = {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            
            params = {
                'apikey': NEWSDATA_API_KEY,
                'country': 'us,gb',
                'language': 'en',
                'category': 'top',
                'size': 15,  # Increase size to get more articles to choose from
                '_': str(int(time.time()))  # Add timestamp to prevent caching
            }
            
            logging.info("Fetching fresh news from API")
            response = requests.get(
                'https://newsdata.io/api/1/news', 
                params=params, 
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('results', [])
                
                if not articles:
                    logging.warning("News API returned no articles")
                    return False
                    
                logging.info(f"Received {len(articles)} articles from news API")
                
                if articles:                with db_session() as session:
                        # Clear old articles
                        session.query(NewsArticle).delete()
                        
                        # Process breaking news - use the freshest article
                        # Sort by published date
                        breaking_news = None
                        try:
                            sorted_articles = sorted(
                                articles, 
                                key=lambda a: datetime.fromisoformat(a['pubDate'].replace('Z', '+00:00')) if 'pubDate' in a else datetime.min,
                                reverse=True  # Most recent first
                            )
                            
                            if sorted_articles:
                                breaking_news = cls._process_article(sorted_articles[0], is_breaking=True)
                                if breaking_news:
                                    session.add(breaking_news)
                                    logging.info(f"Added breaking news: {breaking_news.title}")
                                else:
                                    logging.warning("Failed to process breaking news article")
                        except Exception as e:
                            logging.error(f"Error processing breaking news: {str(e)}")
                            breaking_news = None
                        
                        # Process other news
                        other_news = []
                        seen_titles = set()
                        
                        if breaking_news:
                            seen_titles.add(breaking_news.title)

                        try:
                            # Process up to 6 total articles (1 breaking + 5 others)
                            for article in articles:
                                if len(other_news) >= 5:  # Stop after getting 5 additional articles
                                    break
                                    
                                title = article.get('title', '')
                                if title and title not in seen_titles:
                                    seen_titles.add(title)
                                    news_article = cls._process_article(article)
                                    if news_article:
                                        other_news.append(news_article)
                                        logging.info(f"Added regular news: {news_article.title}")
                        except Exception as e:
                            logging.error(f"Error processing regular news: {str(e)}")

                        session.add_all(other_news)
                        session.commit()

                        # Update cache with correct counts
                        cls._cache.update({
                            'articles': {
                                'breaking': breaking_news,
                                'other': other_news
                            },
                            'breaking': breaking_news,
                            'other': other_news,
                            'last_fetch': current_time,
                            'next_update': current_time + timedelta(seconds=3600),  # Reduced to 1 hour
                            'total': len(other_news) + (1 if breaking_news else 0)  # Add total count
                        })

                        logging.info(f"Updated news at {current_time}, total articles: {len(other_news) + (1 if breaking_news else 0)}")
                        return True
            else:
                logging.error(f"News API returned status code {response.status_code}")
            
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
                    'other': other_news if other_news else [],
                    'total': len(other_news) + (1 if breaking_news else 0)
                }
                
                # Update cache
                cls._cache['articles'] = articles
                cls._cache['last_fetch'] = current_time
                cls._cache['next_update'] = current_time + timedelta(seconds=instance.breaking_news_check_interval)
                
                return articles
                
        except Exception as e:
            logging.error(f"Error getting cached news: {e}")
            return {
                'breaking': None,
                'other': [],
                'total': 0
            }

    @classmethod
    def get_next_update_time(cls):
        instance = cls.get_instance()
        current_time = datetime.utcnow()
        if not instance.next_update_time:
            instance.next_update_time = current_time + timedelta(seconds=instance.breaking_news_check_interval)
        return instance.next_update_time