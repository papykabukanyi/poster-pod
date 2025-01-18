# Create new model activity_log.py
from datetime import datetime
from models.base import Base
from sqlalchemy import Column, Integer, String, DateTime, Text

class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    type = Column(String(50))  # 'post', 'engage', 'error'
    message = Column(Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'type': self.type,
            'message': self.message
        }