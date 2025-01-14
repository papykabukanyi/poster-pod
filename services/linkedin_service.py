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
        # Initialize Gemini with error handling
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            logging.info("Gemini AI initialized successfully")
        except AttributeError:
            logging.warning("Using fallback caption generation - Gemini AI initialization failed")
            self.model = None
        logging.info("LinkedIn service initialized")

    def _get_access_token(self):
        """Get LinkedIn access token using client credentials"""
        try:
            url = "https://www.linkedin.com/oauth/v2/accessToken"
            # Strip any quotes from secret
            client_secret = LINKEDIN_CLIENT_SECRET.strip('"\'')
            
            data = {
                "grant_type": "client_credentials",
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": client_secret
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logging.info(f"Requesting access token with client ID: {LINKEDIN_CLIENT_ID[:8]}...")
            response = requests.post(url, data=data, headers=headers)
            
            logging.info(f"Token response status: {response.status_code}")
            response_data = response.json()
            logging.info(f"Token response: {json.dumps(response_data, indent=2)}")
            
            if response.status_code == 200:
                self.access_token = response_data.get("access_token")
                if self.access_token:
                    logging.info("Successfully obtained access token")
                    return True
                    
            logging.error(f"Failed to get token. Response: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Token error: {str(e)}")
            return False

    def _generate_caption(self, article):
        """Generate caption with fallback"""
        try:
            if not self.model:
                # Fallback caption if Gemini fails
                return f"""Breaking News Update:

{article.title}

Read more at www.onposter.site/news

#BreakingNews #News #CurrentEvents"""

            prompt = f"""Create a LinkedIn post for this news article:
            Title: {article.title}
            Description: {article.description}
            Format: Summary + Company Tags + Hashtags"""
            
            response = self.model.generate_content(prompt)
            return response.text if response else None
        except Exception as e:
            logging.error(f"Caption generation error: {str(e)}")
            # Return fallback caption
            return f"{article.title}\n\nRead more at www.onposter.site/news\n\n#BreakingNews"

    def post_article(self, article):
        """Post article to LinkedIn"""
        try:
            logging.info(f"Attempting to post article: {article.title}")
            
            if not self.access_token and not self._get_access_token():
                logging.error("Failed to obtain access token")
                return False

            caption = self._generate_caption(article)
            if not caption:
                logging.error("Failed to generate caption")
                return False

            image_url = urljoin("https://www.onposter.site", article.image_url)
            logging.info(f"Using image URL: {image_url}")

            # Register image with LinkedIn first
            register_image_url = f"{self.BASE_URL}/assets?action=registerUpload"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:organization:{LINKEDIN_ORG_ID}",
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }]
                }
            }
            
            logging.info("Registering image with LinkedIn")
            register_response = requests.post(register_image_url, headers=headers, json=register_data)
            
            if register_response.status_code != 200:
                logging.error(f"Image registration failed: {register_response.text}")
                return False
                
            upload_url = register_response.json()["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset_id = register_response.json()["value"]["asset"]
            logging.info(f"Image registered successfully. Asset ID: {asset_id}")

            # Upload image to LinkedIn
            logging.info("Uploading image to LinkedIn")
            image_response = requests.get(image_url)
            upload_response = requests.post(upload_url, data=image_response.content, headers={
                "Authorization": f"Bearer {self.access_token}"
            })

            if upload_response.status_code != 201:
                logging.error(f"Image upload failed: {upload_response.text}")
                return False

            # Create post with uploaded image
            post_data = {
                "author": f"urn:li:organization:{LINKEDIN_ORG_ID}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": caption
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": article.title
                                },
                                "media": asset_id,
                                "title": {
                                    "text": article.title
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            logging.info("Creating LinkedIn post")
            logging.debug(f"Post data: {json.dumps(post_data, indent=2)}")
            
            response = requests.post(
                f"{self.BASE_URL}/ugcPosts",
                headers=headers,
                json=post_data
            )

            if response.status_code == 201:
                logging.info("Successfully posted to LinkedIn!")
                return True
                
            logging.error(f"Post creation failed: {response.text}")
            return False
            
        except Exception as e:
            logging.error(f"Post creation error: {str(e)}")
            return False