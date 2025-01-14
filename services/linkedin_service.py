import os
import requests
import google.generativeai as genai
from datetime import datetime
from config import GEMINI_API_KEY, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_ORG_ID
from urllib.parse import urljoin
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] LinkedIn: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class LinkedInService:
    BASE_URL = "https://api.linkedin.com/v2"
    
    def __init__(self):
        self.access_token = None
        self._get_access_token()  # Get token on initialization
        
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            logging.info("Gemini AI initialized successfully")
        except AttributeError:
            logging.warning("Using fallback caption generation")
            self.model = None
        logging.info("LinkedIn service initialized")

    def _get_access_token(self):
        """Get LinkedIn access token using OAuth 2.0"""
        try:
            auth_url = "https://www.linkedin.com/oauth/v2/accessToken"
            data = {
                "grant_type": "client_credentials",
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET.strip("'\""),
                "scope": "w_member_social w_organization_social rw_organization_admin"
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            logging.info("Requesting new access token")
            response = requests.post(auth_url, data=data, headers=headers)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                logging.info("Successfully obtained new access token")
                return True
            
            logging.error(f"Token request failed: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Token error: {str(e)}")
            return False

    def post_article(self, article):
        """Post article to LinkedIn"""
        try:
            if not self.access_token and not self._get_access_token():
                logging.error("No valid access token")
                return False

            caption = self._generate_caption(article)
            if not caption:
                logging.error("Failed to generate caption")
                return False

            # Use full URL for image
            image_url = urljoin("https://www.onposter.site", article.image_url)
            logging.info(f"Using image URL: {image_url}")

            # LinkedIn v2 API post format
            post_data = {
                "author": f"urn:li:organization:{LINKEDIN_ORG_ID}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": caption
                        },
                        "shareMediaCategory": "ARTICLE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": article.description[:100] + "..."
                                },
                                "originalUrl": "https://www.onposter.site/news",
                                "title": {
                                    "text": article.title
                                },
                                "thumbnailUrl": image_url
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202304",
                "Content-Type": "application/json"
            }

            logging.info("Creating LinkedIn post")
            response = requests.post(
                f"{self.BASE_URL}/ugcPosts",
                headers=headers,
                json=post_data
            )

            logging.info(f"Response Status: {response.status_code}")
            logging.info(f"Response Body: {response.text}")

            if response.status_code in [201, 200]:
                logging.info("Successfully posted to LinkedIn!")
                return True
                
            if response.status_code == 401:
                logging.info("Token expired, requesting new token")
                if self._get_access_token():
                    # Retry once with new token
                    return self.post_article(article)
                    
            logging.error(f"Post failed: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Post error: {str(e)}")
            return False

    def _generate_caption(self, article):
        """Generate caption with fallback"""
        try:
            if not self.model:
                return self._get_fallback_caption(article)

            prompt = f"""
            Create an engaging LinkedIn post about this news:
            Title: {article.title}
            Description: {article.description}
            
            Format:
            1. 2-3 engaging sentences
            2. Add 3 relevant #hashtags
            3. End with: Read more at www.onposter.site/news
            """
            
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            return self._get_fallback_caption(article)
            
        except Exception as e:
            logging.error(f"Caption error: {str(e)}")
            return self._get_fallback_caption(article)

    def _get_fallback_caption(self, article):
        """Generate a simple fallback caption"""
        return f"""Breaking News Update:

{article.title}

Read more at www.onposter.site/news

#BreakingNews #GlobalNews #CurrentEvents"""