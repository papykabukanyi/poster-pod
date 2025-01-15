# services/linkedin_token_service.py
import json
import os
from datetime import datetime, timedelta
import requests
import logging
from config import (
    LINKEDIN_CLIENT_ID, 
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    LINKEDIN_TOKEN_FILE
)

class LinkedInTokenService:
    @staticmethod
    def get_stored_token():
        try:
            if os.path.exists(LINKEDIN_TOKEN_FILE):
                with open(LINKEDIN_TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                    if datetime.fromisoformat(token_data['expires_at']) > datetime.now():
                        return token_data['access_token']
            return None
        except Exception as e:
            logging.error(f"Error reading token: {e}")
            return None

    @staticmethod
    def store_token(token_data):
        try:
            expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
            token_info = {
                'access_token': token_data['access_token'],
                'expires_at': expires_at.isoformat()
            }
            with open(LINKEDIN_TOKEN_FILE, 'w') as f:
                json.dump(token_info, f)
            return True
        except Exception as e:
            logging.error(f"Error storing token: {e}")
            return False