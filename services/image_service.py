import os
import requests
from bs4 import BeautifulSoup
from config import UNSPLASH_ACCESS_KEY
import hashlib
from PIL import Image
from io import BytesIO
import time

class ImageService:
    used_images = set()
    image_cache = {}
    cache_timeout = 3600  # 1 hour cache

    @staticmethod
    def compress_image(image_data, max_size=(800, 800), quality=85):
        """Compress image to reduce size while maintaining quality"""
        try:
            img = Image.open(BytesIO(image_data))
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
        except Exception as e:
            print(f"Error compressing image: {e}")
            return image_data

    @staticmethod
    def get_image_hash(url):
        """Generate hash for image URL"""
        return hashlib.md5(url.encode()).hexdigest()

    @classmethod
    def get_cached_image(cls, url, save_path):
        """Get image from cache or download"""
        try:
            image_hash = cls.get_image_hash(url)
            current_time = time.time()

            # Check if image is cached and still valid
            if image_hash in cls.image_cache:
                cached_data = cls.image_cache[image_hash]
                if current_time - cached_data['timestamp'] < cls.cache_timeout:
                    if os.path.exists(cached_data['path']):
                        return cached_data['path']

            # Download and cache image
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                # Compress image
                compressed_data = cls.compress_image(response.content)
                
                # Save compressed image
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(compressed_data)

                # Update cache
                cls.image_cache[image_hash] = {
                    'path': save_path,
                    'timestamp': current_time
                }
                return save_path

            return None
        except Exception as e:
            print(f"Error caching image: {e}")
            return None

    @staticmethod
    def get_article_image(url):
        """Extract image from article URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different meta tags for images
                for meta in [
                    ('property', 'og:image'),
                    ('name', 'twitter:image'),
                    ('property', 'og:image:secure_url'),
                    ('itemprop', 'image')
                ]:
                    image_tag = soup.find('meta', {meta[0]: meta[1]})
                    if image_tag and image_tag.get('content'):
                        return image_tag.get('content')
                
                # Try finding first article image
                article_img = soup.find('article')
                if article_img:
                    img = article_img.find('img')
                    if img and img.get('src'):
                        return img.get('src')
                        
            return None
        except Exception as e:
            print(f"Error extracting article image: {e}")
            return None

    @classmethod
    def generate_news_image(cls, title, news_url=None, save_path=None):
        """Generate or get image for news article"""
        try:
            # Try to get image from article first
            if news_url:
                article_image = cls.get_article_image(news_url)
                if article_image:
                    return cls.get_cached_image(article_image, save_path)

            # Fallback to Unsplash with specific search
            keywords = [word.lower() for word in title.split() 
                       if len(word) > 3 and word.lower() not in 
                       {'the', 'and', 'for', 'that', 'with', 'this', 'from'}][:3]
            
            if not keywords:
                keywords = ['news']

            params = {
                "query": f"{' '.join(keywords)} news",
                "orientation": "landscape",
                "per_page": 5  # Get multiple options
            }
            
            headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    # Find first unused image
                    for result in data['results']:
                        image_url = result['urls']['regular']
                        if image_url not in cls.used_images:
                            cls.used_images.add(image_url)
                            return cls.get_cached_image(image_url, save_path)

            return None
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    @staticmethod
    def clear_used_images():
        """Clear the used images cache"""
        ImageService.used_images.clear()