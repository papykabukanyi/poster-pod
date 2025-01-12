import os
import requests
from bs4 import BeautifulSoup
from config import UNSPLASH_ACCESS_KEY

class ImageService:
    used_images = set()
    
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

    @staticmethod
    def generate_news_image(title, news_url=None, save_path=None):
        try:
            # First try to get image from article
            if news_url:
                article_image = ImageService.get_article_image(news_url)
                if article_image:
                    try:
                        img_response = requests.get(article_image, timeout=5)
                        if img_response.status_code == 200:
                            if save_path:
                                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                with open(save_path, 'wb') as f:
                                    f.write(img_response.content)
                                return save_path
                            return img_response.content
                    except Exception as e:
                        print(f"Error saving article image: {e}")

            # Fallback to Unsplash
            keywords = [word.lower() for word in title.split() 
                       if len(word) > 3 and word.lower() not in 
                       {'the', 'and', 'for', 'that', 'with', 'this', 'from'}]
            
            search_query = ' '.join(keywords[:3])
            
            params = {
                "query": f"{search_query} news",
                "orientation": "landscape",
                "per_page": 1
            }
            
            headers = {
                "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
            }

            response = requests.get(
                "https://api.unsplash.com/search/photos",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    image_url = data['results'][0]['urls']['regular']
                    
                    if image_url not in ImageService.used_images:
                        ImageService.used_images.add(image_url)
                        img_response = requests.get(image_url)
                        
                        if img_response.status_code == 200:
                            if save_path:
                                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                with open(save_path, 'wb') as f:
                                    f.write(img_response.content)
                                return save_path
                            return img_response.content
            
            return None
            
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    @staticmethod
    def clear_used_images():
        """Clear the used images cache"""
        ImageService.used_images.clear()