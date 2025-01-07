import os
from dotenv import load_dotenv

load_dotenv()

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

# Database configuration
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')