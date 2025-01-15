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
    last_update_time = None
    next_update_time = None
    breaking_news_check_interval = 7200  # 2 hours in seconds
    last_fetch_time = None
    seen_articles = set()
    linkedin_service = LinkedInService()
    last_linkedin_post = None
    linkedin_post_interval = 7200  # 2 hours in seconds
    twitter_service = TwitterService()  
    last_twitter_post = None
    cached_articles = {
        'breaking': None,
        'other': [],
        'last_fetch': None
    }
    
    # Class-level cache for sharing across instances
    _cache = {
        'articles': None,
        'last_fetch': None,
        'next_update': None
    }
    
    @classmethod
    def fetch_news(cls, force_breaking=False):
        try:
            current_time = datetime.utcnow()
            
            # Return cached news if valid
            if not force_breaking and cls.cached_articles['last_fetch']:
                time_since_cache = (current_time - cls.cached_articles['last_fetch']).total_seconds()
                if time_since_cache < cls.breaking_news_check_interval:
                    logging.info("Using cached news articles")
                    return True
            
            # Only fetch if forcing or time has elapsed
            if not force_breaking and cls.next_update_time and current_time < cls.next_update_time:
                logging.info("Skipping fetch - not time yet")
                return
                
            # Update timing
            cls.last_update_time = current_time
            cls.next_update_time = current_time + timedelta(seconds=cls.breaking_news_check_interval)
            
            cls.last_fetch_time = current_time
            ImageService.clear_used_images()
            
            # Fetch latest news from NewsData.io API
            params = {
                'apikey': NEWSDATA_API_KEY,
                'country': 'us,gb',  # English news sources
                'language': 'en',
                'category': 'top',   # Top stories
                'size': 10          # Get more articles to ensure fresh content
            }
            
            url = 'https://newsdata.io/api/1/news'
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                articles = response.json().get('results', [])
                
                if articles:
                    with db_session() as session:
                        current_breaking = session.query(NewsArticle).filter_by(is_breaking=True).first()
                        
                        # Check if we have a newer breaking news
                        latest_article = articles[0]
                        latest_date = datetime.fromisoformat(latest_article['pubDate'].replace('Z', '+00:00'))
                        
                        if not current_breaking or latest_date > current_breaking.published_at:
                            # Clear old news
                            session.query(NewsArticle).delete()
                            
                            # Process breaking news
                            breaking_news = cls._fetch_news(latest_article, is_breaking=True)
                            if breaking_news:
                                session.add(breaking_news)
                            
                            # Process other news
                            seen_titles = {latest_article['title']}
                            other_articles = []
                            
                            for article in articles[1:]:
                                if len(other_articles) >= 3:
                                    break
                                    
                                if article['title'] not in seen_titles:
                                    seen_titles.add(article['title'])
                                    news_article = cls._fetch_news(article)
                                    if news_article:
                                        other_articles.append(news_article)
                            
                            session.add_all(other_articles)
                            session.commit()
                            cls.last_update_time = current_time
                            print(f"Updated news at {current_time} with {len(other_articles) + 1} articles")
                        else:
                            print("No newer breaking news found")
                else:
                    print("No articles found from API")
            else:
                print(f"API request failed with status {response.status_code}")

            # Update cache after successful fetch
            if articles:
                with db_session() as session:
                    cls.cached_articles['breaking'] = breaking_news
                    cls.cached_articles['other'] = other_articles
                    cls.cached_articles['last_fetch'] = current_time

        except Exception as e:
            print(f"Error fetching news: {e}")

    @classmethod
    def _fetch_news(cls, article, is_breaking=False):
        try:
            # Add current_time definition at the start
            current_time = datetime.utcnow()
            
            # Create consistent hash for article
            article_hash = hashlib.md5(
                f"{article['title']}{article['description']}".encode()
            ).hexdigest()

            # Skip if duplicate
            if article_hash in cls.seen_articles:
                return None
            cls.seen_articles.add(article_hash)

            # Generate consistent image path
            image_path = f"static/images/generated/{article_hash}.jpg"
            final_image_path = None

            # Try to get existing image first
            if os.path.exists(image_path):
                final_image_path = image_path
            else:
                # Try article image
                if article.get('image_url'):
                    final_image_path = ImageService.get_cached_image(
                        article['image_url'],
                        image_path
                    )
                
                # Fallback to generated image
                if not final_image_path:
                    final_image_path = ImageService.generate_news_image(
                        article['title'],
                        article['link'],
                        image_path
                    )

            pub_date = datetime.fromisoformat(article['pubDate'].replace('Z', '+00:00'))
            news_article = NewsArticle(
                title=article['title'],
                description=article['description'],
                url=article['link'],
                image_url=f"/{image_path}" if final_image_path else None,
                published_at=pub_date,
                source=article['source_id'],
                category='breaking' if is_breaking else 'news',
                is_breaking=is_breaking
            )

            # Post to social media if breaking news
            if is_breaking:
                # LinkedIn posting (existing code)
                if (not cls.last_linkedin_post or 
                    current_time - cls.last_linkedin_post >= timedelta(seconds=cls.linkedin_post_interval)):
                    if cls.linkedin_service.post_article(news_article):
                        cls.last_linkedin_post = current_time

                # Twitter posting
                if (not cls.last_twitter_post or 
                    current_time - cls.last_twitter_post >= timedelta(seconds=1800)):  # 30 minutes
                    if cls.twitter_service.post_article(news_article):
                        cls.last_twitter_post = current_time

            return news_article

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
                    cls.fetch_news()
                    time.sleep(cls.breaking_news_check_interval)
                    
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
        if cls.fetch_news(force_breaking=True):
            cls.last_update_time = current_time
            cls.next_update_time = current_time + timedelta(seconds=cls.breaking_news_check_interval)

    @classmethod
    def get_cached_news(cls):
        """Get news from cache or database"""
        current_time = datetime.utcnow()
        
        # Return cache if valid
        if cls._cache['articles'] and cls._cache['next_update']:
            if current_time < cls._cache['next_update']:
                logging.info("Using cached news")
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
            if not cls._cache['next_update']:
                cls._cache['next_update'] = current_time + timedelta(seconds=cls.breaking_news_check_interval)
            
            return articles