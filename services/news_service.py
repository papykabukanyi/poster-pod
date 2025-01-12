import os
import requests
import threading
import time
from datetime import datetime, timedelta
from models.news import NewsArticle
from models.base import db_session
from config import NEWS_API_KEY
from services.image_service import ImageService
import os

class NewsService:
    last_update_time = None
    breaking_news_check_interval = 300  # Check every 5 minutes for breaking news
    
    @classmethod
    def fetch_news(cls, force_breaking=False):
        try:
            current_time = datetime.utcnow()
            cls.last_update_time = current_time
            ImageService.clear_used_images()
            
            # Fetch latest breaking news
            breaking_news = cls._fetch_breaking_news()
            
            with db_session() as session:
                current_breaking = session.query(NewsArticle).filter_by(is_breaking=True).first()
                
                # If we found new breaking news that's different from current
                if breaking_news and (not current_breaking or 
                    breaking_news[0].title != current_breaking.title):
                    
                    # Archive old breaking news
                    if current_breaking:
                        current_breaking.is_breaking = False
                    
                    # Add new breaking news
                    session.add_all(breaking_news)
                    cls.last_update_time = current_time
                    
                elif not force_breaking:
                    # Regular 30-minute update
                    all_news = cls._fetch_latest_news()
                    if all_news:
                        session.query(NewsArticle).delete()
                        session.add_all(all_news)
                
                session.commit()

        except Exception as e:
            print(f"Error fetching news: {e}")

    @classmethod
    def _fetch_latest_news(cls):
        url = 'https://newsapi.org/v2/everything'
        current_time = datetime.utcnow()
        
        # Define search queries for different categories
        search_queries = [
            ('technology', 'tech'),
            ('breaking news', 'breaking'),
            ('world news', 'world'),
            ('business', 'business'),
            ('science', 'science'),
            ('health', 'health')
        ]
        
        all_articles = []
        seen_titles = set()
        
        for query, category in search_queries:
            params = {
                'q': f'"{query}" AND (breaking OR latest OR update)',
                'apiKey': NEWS_API_KEY,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 10,  # Get more articles per category
                'from': (current_time - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M')  # Last 12 hours
            }

            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    articles = response.json().get('articles', [])
                    
                    for article in articles:
                        title = article.get('title')
                        if not title or title in seen_titles or not article.get('description'):
                            continue
                            
                        seen_titles.add(title)
                        
                        # Generate unique image based on title and category
                        image_path = f"static/images/generated/{category}_{abs(hash(title))}.jpg"
                        generated_image = ImageService.generate_news_image(
                            f"{category} {title}",
                            save_path=image_path
                        )
                        
                        all_articles.append(NewsArticle(
                            title=title,
                            description=article.get('description'),
                            url=article.get('url'),
                            image_url=f"/{image_path}" if generated_image else None,
                            published_at=datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'),
                            source=article['source']['name'],
                            category=category,
                            is_breaking=False  # Will be set later for the latest
                        ))
                        
                        if len(all_articles) >= 4:  # Keep collecting until we have at least 4 unique articles
                            break
                            
            except Exception as e:
                print(f"Error fetching {category} news: {e}")
                continue

        # Sort all articles by published date to get the most recent
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        
        # Take only the 4 most recent articles
        return all_articles[:4]

    @classmethod
    def _fetch_breaking_news(cls):
        url = 'https://newsapi.org/v2/everything'
        current_time = datetime.utcnow()
        
        params = {
            'q': '(breaking OR urgent OR alert) AND (world OR global OR international)',
            'apiKey': NEWS_API_KEY,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 1,
            'from': (current_time - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M')
        }

        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                if articles:
                    article = articles[0]
                    # Generate image with breaking news context
                    image_path = f"static/images/generated/breaking_{abs(hash(article['title']))}.jpg"
                    generated_image = ImageService.generate_news_image(
                        f"breaking news {article['title']}",
                        save_path=image_path
                    )
                    
                    return [NewsArticle(
                        title=article['title'],
                        description=article['description'],
                        url=article['url'],
                        image_url=f"/{image_path}" if generated_image else None,
                        published_at=datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'),
                        source=article['source']['name'],
                        category='breaking',
                        is_breaking=True
                    )]
        except Exception as e:
            print(f"Error fetching breaking news: {e}")
        return None

    @classmethod
    def start_scheduler(cls):
        def run_scheduler():
            regular_update_interval = 1800  # 30 minutes
            breaking_check_interval = 300   # 5 minutes
            last_regular_update = datetime.utcnow()
            
            while True:
                try:
                    current_time = datetime.utcnow()
                    
                    # Check for breaking news every 5 minutes
                    cls.fetch_news(force_breaking=True)
                    
                    # Regular update every 30 minutes
                    if (current_time - last_regular_update).total_seconds() >= regular_update_interval:
                        cls.fetch_news(force_breaking=False)
                        last_regular_update = current_time
                    
                    time.sleep(breaking_check_interval)
                    
                except Exception as e:
                    print(f"Scheduler error: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()