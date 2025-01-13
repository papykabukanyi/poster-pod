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
            # Convert RGBA to RGB
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Resize if needed
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
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
        """Get image from cache or download with better error handling"""
        try:
            image_hash = cls.get_image_hash(url)
            current_time = time.time()
            
            # Check filesystem cache first
            if os.path.exists(save_path):
                # Update cache metadata
                cls.image_cache[image_hash] = {
                    'path': save_path,
                    'timestamp': current_time
                }
                return save_path

            # Try to download image
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                # Ensure directory exists
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # Compress and save image
                compressed_data = cls.compress_image(response.content)
                if compressed_data:
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
            print(f"Error caching image from {url}: {e}")
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
        """Generate or get image with better caching"""
        try:
            # Use hash of title for consistent image naming
            title_hash = cls.get_image_hash(title)
            image_path = save_path or f"static/images/generated/{title_hash}.jpg"
            
            # Check if image already exists
            if os.path.exists(image_path):
                return image_path
                
            # Try to get image from article
            if news_url:
                article_image = cls.get_article_image(news_url)
                if article_image:
                    cached_image = cls.get_cached_image(article_image, image_path)
                    if cached_image:
                        return cached_image

            # Fallback to Unsplash with cached results
            keywords = [word.lower() for word in title.split() 
                       if len(word) > 3 and word.lower() not in 
                       {'the', 'and', 'for', 'that', 'with', 'this', 'from'}][:3]
            
            if not keywords:
                keywords = ['news']

            search_query = f"{' '.join(keywords)} news"
            params = {
                "query": search_query,
                "orientation": "landscape",
                "per_page": 5
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
                    # Try each result until we get a valid image
                    for result in data['results']:
                        image_url = result['urls']['regular']
                        if image_url not in cls.used_images:
                            cached_image = cls.get_cached_image(image_url, image_path)
                            if cached_image:
                                cls.used_images.add(image_url)
                                return cached_image

            return None
        except Exception as e:
            print(f"Error generating image for {title}: {e}")
            return None

    @staticmethod
    def clear_used_images():
        """Clear the used images cache"""
        ImageService.used_images.clear()