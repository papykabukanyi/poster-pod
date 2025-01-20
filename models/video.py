# models/video.py
from models.base import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets

class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    slug = Column(String(16), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    duration = Column(Float)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)  # Make sure this exists
    cloudinary_public_id = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    comments = Column(JSON, default=lambda: [])

    def __init__(self, **kwargs):
        super(Video, self).__init__(**kwargs)
        if not self.slug:
            self.slug = secrets.token_urlsafe(12)
        if self.comments is None:
            self.comments = []
        if self.likes is None:
            self.likes = 0

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'title': self.title,
            'description': self.description,
            'video_url': self.video_url,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'views': self.views,
            'likes': self.likes,  # Add this
            'created_at': self.created_at.isoformat(),
            'comments': self.comments
        }