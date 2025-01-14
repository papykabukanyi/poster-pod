from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime
from models.base import Base

class NewsArticle(Base):
    __tablename__ = 'news_articles'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    url = Column(Text)  # Changed from String(500) to Text
    image_url = Column(Text)  # Changed from String(500) to Text
    published_at = Column(DateTime)
    source = Column(String(100))
    category = Column(String(50))  # 'breaking', 'tech', 'tech_politics'
    is_breaking = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'image_url': self.image_url,
            'published_at': self.published_at,
            'source': self.source,
            'category': self.category,
            'is_breaking': self.is_breaking
        }