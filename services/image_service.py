import requests
import os
from config import UNSPLASH_ACCESS_KEY

class ImageService:
    # Keep track of used images to avoid duplicates
    used_images = set()
    
    @staticmethod
    def generate_news_image(title, news_url=None, save_path=None):
        try:
            # First try to get image from news source if URL provided
            if news_url:
                try:
                    response = requests.get(news_url, timeout=5)
                    if response.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response.text, 'html.parser')
                        og_image = soup.find('meta', property='og:image')
                        if og_image and og_image.get('content'):
                            img_response = requests.get(og_image['content'])
                            if img_response.status_code == 200:
                                if save_path:
                                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                    with open(save_path, 'wb') as f:
                                        f.write(img_response.content)
                                    return save_path
                                return img_response.content
                except Exception as e:
                    print(f"Error getting news image: {e}")

            # If no news image, use Unsplash with better search terms
            keywords = [word.lower() for word in title.split() 
                       if len(word) > 3 and word.lower() not in 
                       {'the', 'and', 'for', 'that', 'with', 'this', 'from', 'have', 'will'}]
            
            # Create specific search query based on news content
            search_query = ' '.join(keywords[:3])  # Use first 3 meaningful words
            
            params = {
                "query": f"{search_query} news",
                "orientation": "landscape",
                "per_page": 30,
                "content_filter": "high"
            }
            
            headers = {
                "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
            }

            response = requests.get("https://api.unsplash.com/search/photos", 
                                 headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data['results']:
                    # Filter out used images
                    available_images = [img for img in data['results'] 
                                     if img['urls']['regular'] not in ImageService.used_images]
                    
                    if available_images:
                        # Pick random image from available ones
                        import random
                        image = random.choice(available_images)
                        image_url = image['urls']['regular']
                        
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