# services/twitter_token_service.py
import os
import json
import logging
from datetime import datetime, timedelta
from config import (
    TWITTER_CLIENT_ID,
    TWITTER_CLIENT_SECRET,
    TWITTER_TOKEN_FILE
)

class TwitterTokenService:
    @staticmethod
    def get_stored_token():
        try:
            if os.path.exists(TWITTER_TOKEN_FILE):
                with open(TWITTER_TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                    if datetime.fromisoformat(token_data['expires_at']) > datetime.now():
                        return token_data['access_token']
            return None
        except Exception as e:
            logging.error(f"Error reading Twitter token: {e}")
            return None

    @staticmethod
    def store_token(token_data):
        try:
            expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
            token_info = {
                'access_token': token_data['access_token'],
                'expires_at': expires_at.isoformat()
            }
            with open(TWITTER_TOKEN_FILE, 'w') as f:
                json.dump(token_info, f)
            return True
        except Exception as e:
            logging.error(f"Error storing Twitter token: {e}")
            return False