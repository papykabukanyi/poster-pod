import requests
import os
from config import UNSPLASH_ACCESS_KEY

class ImageService:
    # Keep track of used images to avoid duplicates
    used_images = set()
    
    @staticmethod
    def generate_news_image(title, save_path=None):
        try:
            # Extract meaningful keywords from title
            keywords = [word.lower() for word in title.split() 
                       if len(word) > 3 and word.lower() not in 
                       {'the', 'and', 'for', 'that', 'with', 'this', 'from', 'have', 'will'}]
            
            # Use different keyword combinations for variety
            search_queries = [
                f"technology {' '.join(keywords[:2])}",
                f"tech news {keywords[0] if keywords else 'digital'}",
                f"digital {' '.join(keywords[-2:] if len(keywords) > 1 else keywords)}",
                f"future {keywords[0] if keywords else 'technology'}"
            ]
            
            for query in search_queries:
                params = {
                    "query": query,
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
                        # Filter out already used images
                        available_images = [img for img in data['results'] 
                                         if img['urls']['regular'] not in ImageService.used_images]
                        
                        if available_images:
                            # Pick random image from available ones
                            import random
                            image = random.choice(available_images)
                            image_url = image['urls']['regular']
                            
                            # Mark image as used
                            ImageService.used_images.add(image_url)
                            
                            img_response = requests.get(image_url)
                            if img_response.status_code == 200:
                                if save_path:
                                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                    with open(save_path, 'wb') as f:
                                        f.write(img_response.content)
                                    return save_path
                                return img_response.content
            
            # Clear used images cache if too large
            if len(ImageService.used_images) > 1000:
                ImageService.used_images.clear()
                
            return None
            
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    @staticmethod
    def clear_used_images():
        """Clear the used images cache"""
        ImageService.used_images.clear()