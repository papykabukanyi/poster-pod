import os
import requests
import google.generativeai as genai
from datetime import datetime
from config import GEMINI_API_KEY, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_ORG_ID
from urllib.parse import urljoin
import logging
import json
from services.linkedin_token_service import LinkedInTokenService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] LinkedIn: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class LinkedInService:
    BASE_URL = "https://api.linkedin.com/v2"
    
    def __init__(self):
        self.access_token = LinkedInTokenService.get_stored_token()
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            logging.info("Gemini AI initialized successfully")
        except AttributeError:
            logging.warning("Using fallback caption generation")
            self.model = None
        logging.info("LinkedIn service initialized")

    def _refresh_token(self):
        """Get new access token"""
        try:
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            data = {
                'grant_type': 'refresh_token',
                'client_id': LINKEDIN_CLIENT_ID,
                'client_secret': LINKEDIN_CLIENT_SECRET,
                'refresh_token': self.access_token
            }
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            response = requests.post(token_url, data=data, headers=headers)
            if response.status_code == 200:
                token_data = response.json()
                LinkedInTokenService.store_token(token_data)
                self.access_token = token_data['access_token']
                return True
            return False
        except Exception as e:
            logging.error(f"Token refresh error: {e}")
            return False

    def _get_member_id(self):
        """Get LinkedIn member ID from /me endpoint"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202401"
            }
            
            response = requests.get(f"{self.BASE_URL}/me", headers=headers)
            if response.status_code == 200:
                self.member_id = response.json().get('id')
                logging.info(f"Got member ID: {self.member_id}")
                return True
            
            logging.error(f"Failed to get member ID: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Member ID error: {e}")
            return False

    def _get_access_token(self):
        """Get LinkedIn access token"""
        try:
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            data = {
                'grant_type': 'client_credentials',
                'client_id': LINKEDIN_CLIENT_ID,
                'client_secret': LINKEDIN_CLIENT_SECRET.strip('"\''),
                'scope': 'w_member_social w_organization_social rw_organization_admin'
            }
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(token_url, data=data, headers=headers)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                logging.info("Successfully obtained LinkedIn token")
                return True
                
            logging.error(f"Token request failed: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Token error: {e}")
            return False

    def post_article(self, article):
        """Post article using LinkedIn v2 API"""
        try:
            if not self.access_token:
                logging.error("No access token available")
                return False

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202401",
                "Content-Type": "application/json"
            }

            caption = self._generate_caption(article)
            
            post_data = {
                "content": {
                    "contentEntities": [{
                        "entityLocation": "https://www.onposter.site/news",
                        "thumbnails": [{
                            "resolvedUrl": urljoin("https://www.onposter.site", article.image_url)
                        }],
                        "title": article.title
                    }],
                    "title": article.title
                },
                "distribution": {
                    "linkedInDistributionTarget": {
                        "visibleToGuest": True
                    }
                },
                "owner": f"urn:li:organization:{LINKEDIN_ORG_ID}",
                "text": {
                    "text": caption
                }
            }

            logging.info("Creating LinkedIn post")
            response = requests.post(
                f"{self.BASE_URL}/posts",
                headers=headers, 
                json=post_data
            )

            if response.status_code == 401 and self._refresh_token():
                # Retry with new token
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = requests.post(
                    f"{self.BASE_URL}/posts",
                    headers=headers,
                    json=post_data
                )

            logging.info(f"Response Status: {response.status_code}")
            logging.info(f"Response Body: {response.text}")

            return response.status_code in [201, 200]

        except Exception as e:
            logging.error(f"Post error: {str(e)}")
            return False

    def _generate_caption(self, article):
        try:
            if not self.model:
                return self._get_fallback_caption(article)

            prompt = f"""
            Create an engaging LinkedIn post for this news:
            Title: {article.title}
            Description: {article.description}
            
            Format:
            1. 2-3 engaging sentences
            2. Add 3 relevant #hashtags
            3. End with: Read more at www.onposter.site/news
            """
            
            response = self.model.generate_content(prompt)
            return response.text if response else self._get_fallback_caption(article)
            
        except Exception as e:
            logging.error(f"Caption error: {e}")
            return self._get_fallback_caption(article)

    def _get_fallback_caption(self, article):
        return f"""Breaking News Update:\n\n{article.title}\n\nRead more at www.onposter.site/news\n\n#BreakingNews #News #LatestUpdates"""