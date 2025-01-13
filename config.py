import os
from dotenv import load_dotenv

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

# Database configuration
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

# Image settings
IMAGE_CACHE_DIR = 'static/images/generated'
IMAGE_CACHE_TIME = 3600  # 1 hour
MAX_IMAGE_SIZE = (800, 800)
IMAGE_QUALITY = 85