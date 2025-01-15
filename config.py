import os
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
# News API configuration
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
# Add to existing config.py
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# Add to existing config
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')
# Replace NEWS_API_KEY with:
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
# Add to existing config.py
LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID')
LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET')
# Add to existing config.py
LINKEDIN_ORG_ID = os.getenv('LINKEDIN_ORG_ID')
# Add LinkedIn configs
LINKEDIN_REDIRECT_URI = os.getenv('LINKEDIN_REDIRECT_URI')
LINKEDIN_TOKEN_FILE = 'linkedin_token.json'  # Store token locally

# Add to existing config.py
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET')
TWITTER_CLIENT_ID = os.getenv('TWITTER_CLIENT_ID')
TWITTER_CLIENT_SECRET = os.getenv('TWITTER_CLIENT_SECRET')
TWITTER_TOKEN_FILE = 'twitter_token.json'

# Database configuration
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

# Image settings
IMAGE_CACHE_DIR = 'static/images/generated'
IMAGE_CACHE_TIME = 3600  # 1 hour
MAX_IMAGE_SIZE = (800, 800)
IMAGE_QUALITY = 85