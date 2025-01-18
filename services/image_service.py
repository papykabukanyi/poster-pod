from PIL import Image, ImageDraw, ImageFont  # Add ImageDraw and ImageFont
import os
import requests
from bs4 import BeautifulSoup
from config import UNSPLASH_ACCESS_KEY
import hashlib
import tweepy
from io import BytesIO
import time
import logging
from datetime import datetime

# Optional: Add basic logging configuration if not configured elsewhere
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] ImageService: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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

    @staticmethod
    def preload_images(articles):
        """Preload all article images"""
        try:
            preloaded = []
            for article in articles:
                if article.image_url:
                    img_path = article.image_url.lstrip('/')
                    if os.path.exists(img_path):
                        preloaded.append(article.image_url)
                    else:
                        # Try to generate/cache image
                        final_path = ImageService.generate_news_image(
                            article.title,
                            article.url,
                            img_path
                        )
                        if final_path:
                            preloaded.append(f"/{final_path}")
                            
            return preloaded
        except Exception as e:
            logging.error(f"Error preloading images: {e}")
            return []

    @staticmethod
    def add_watermark(image_path, text="www.onposter.site/news | www.onposter.site"):
        """Add text watermark to image"""
        try:
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if needed
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Create a drawing object
                draw = ImageDraw.Draw(img)
                
                # Calculate text size (30% of image width)
                fontsize = int(img.size[0] * 0.03)
                try:
                    font = ImageFont.truetype("Arial.ttf", fontsize)
                except:
                    font = ImageFont.load_default()

                # Calculate text position (bottom center)
                text_width = draw.textlength(text, font=font)
                x = (img.size[0] - text_width) / 2
                y = img.size[1] - (fontsize * 2)

                # Add shadow/outline for better visibility
                for offset in [(1,1), (-1,-1), (1,-1), (-1,1)]:
                    draw.text((x+offset[0], y+offset[1]), text, font=font, fill='black')

                # Draw main text
                draw.text((x,y), text, font=font, fill='white')

                # Save with watermark
                watermarked_path = f"{os.path.splitext(image_path)[0]}_watermarked.jpg"
                img.save(watermarked_path, 'JPEG', quality=85)
                return watermarked_path

        except Exception as e:
            logging.error(f"Error adding watermark: {e}")
            return image_path

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
        
        # Handle image with watermark
        media_id = None
        if article.image_url and os.path.exists(article.image_url.lstrip('/')):
            try:
                # Create watermark path
                original_path = article.image_url.lstrip('/')
                watermark_path = f"{os.path.splitext(original_path)[0]}_watermarked.jpg"
                
                # Add watermark
                watermarked_path = ImageService.add_watermark(
                    original_path,
                    "www.onposter.site/news | www.onposter.site"
                )
                
                if watermarked_path and os.path.exists(watermarked_path):
                    # Upload watermarked image
                    media = self.v1_api.media_upload(watermarked_path)
                    media_id = media.media_id
                    
                    # Clean up watermarked file after upload
                    try:
                        os.remove(watermarked_path)
                    except Exception as e:
                        logging.error(f"Error cleaning up watermarked image: {e}")
                
            except Exception as e:
                logging.error(f"Media processing error: {e}")
                # Continue without image if there's an error

        # Post tweet
        try:
            tweet_params = {'text': caption}
            if media_id:
                tweet_params['media_ids'] = [media_id]
                
            response = self.client.create_tweet(**tweet_params)
            
            if response.data:
                self.last_post_time = current_time
                self.retry_count = 0
                logging.info(f"Successfully posted to Twitter at {current_time}")
                return True

        except tweepy.TweepyException as e:
            if "duplicate" in str(e).lower():
                # Add timestamp to avoid duplicate
                caption = f"{caption} {current_time.strftime('%H:%M:%S')}"
                return self.post_article(article)
            
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                time.sleep(2 ** self.retry_count)
                return self.post_article(article)
                
            logging.error(f"Twitter post error after {self.max_retries} retries: {e}")
            return False

    except Exception as e:
        logging.error(f"Twitter post error: {e}")
        return False