# app.py
from flask import Flask, render_template, request, jsonify, abort, session, make_response
import cloudinary
import cloudinary.uploader
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, text
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from datetime import datetime, timedelta
import json
from config import *
from cloudinary import uploader

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config')
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB limit

# Initialize SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URI)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Timeago filter
def timeago(date):
    now = datetime.utcnow()
    diff = now - date
    
    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = diff.days
    
    if days > 365:
        years = days // 365
        return f"{int(years)}y ago"
    if days > 30:
        months = days // 30
        return f"{int(months)}mo ago"
    if days > 0:
        return f"{int(days)}d ago"
    if hours > 0:
        return f"{int(hours)}h ago"
    if minutes > 0:
        return f"{int(minutes)}m ago"
    return "just now"

app.jinja_env.filters['timeago'] = timeago

class Podcast(Base):
    __tablename__ = 'podcasts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    audio_url = Column(String(500), nullable=False)
    duration = Column(Float)
    likes = Column(Integer, default=0)
    views = Column(Integer, default=0)
    embed_data = Column(JSON, default={}, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    cloudinary_public_id = Column(String(200))  # Add this field

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'audio_url': self.audio_url,
            'duration': self.duration,
            'likes': self.likes,
            'views': self.views,
            'embed_data': self.embed_data if self.embed_data else {},
            'created_at': self.created_at.isoformat(),
            'cloudinary_public_id': self.cloudinary_public_id
        }

@app.route('/')
def index():
    try:
        podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
        return render_template('index.html', podcasts=podcasts)
    except Exception as e:
        print(f"Error in index route: {e}")
        db_session.rollback()
        return "An error occurred loading the podcasts. Please try again.", 500

@app.route('/admin')
def admin():
    try:
        # Get podcasts ordered by creation date (newest first)
        podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
        return render_template('admin.html', podcasts=podcasts)
    except Exception as e:
        print(f"Error in admin route: {e}")
        db_session.rollback()
        return "Error loading admin dashboard", 500

@app.route('/like/<int:podcast_id>', methods=['POST'])
def like_podcast(podcast_id):
    try:
        podcast = Podcast.query.get(podcast_id)
        if not podcast:
            return jsonify({'error': 'Podcast not found'}), 404
        
        session_likes = session.get('likes', {})
        if str(podcast_id) in session_likes:
            return jsonify({'error': 'Already liked'}), 400
        
        podcast.likes += 1
        session_likes[str(podcast_id)] = True
        session['likes'] = session_likes
        
        db_session.commit()
        
        return jsonify({'likes': podcast.likes})
    except Exception as e:
        db_session.rollback()
        print(f"Error in like_podcast: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/upload', methods=['POST'])
def upload_podcast():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    file = request.files['audio']
    title = request.form.get('title', 'Untitled Podcast')
    description = request.form.get('description', '')
    timestamp = request.form.get('timestamp')
    
    upload_key = f"upload_{title}_{timestamp}"
    if upload_key in session:
        return jsonify({'error': 'Duplicate upload detected'}), 400
    
    if file and file.filename.endswith(('.mp3', '.wav', '.m4a')):
        try:
            # Set upload flag in session
            session[upload_key] = True
            
            # Generate unique ID
            unique_id = f"podcast_{int(datetime.utcnow().timestamp())}_{os.urandom(8).hex()}"
            
            # Upload to Cloudinary
            result = uploader.upload(
                file,
                resource_type="auto",
                folder="podcasts/",
                public_id=unique_id,
                overwrite=False,
                unique_filename=True
            )
            
            if not result or 'secure_url' not in result:
                raise Exception("Upload failed")
            
            podcast = Podcast(
                title=title,
                description=description,
                audio_url=result['secure_url'],
                duration=result.get('duration', 0),
                cloudinary_public_id=result['public_id']
            )
            
            db_session.add(podcast)
            db_session.commit()
            
            # Clear upload flag after successful upload
            session.pop(upload_key, None)
            
            return jsonify(podcast.to_dict()), 200
            
        except Exception as e:
            db_session.rollback()
            session.pop(upload_key, None)  # Clear flag on error
            print(f"Upload error: {str(e)}")
            if 'result' in locals() and result.get('public_id'):
                try:
                    uploader.destroy(result['public_id'], resource_type="video")
                except Exception as ce:
                    print(f"Cloudinary cleanup error: {ce}")
            return jsonify({'error': 'Upload failed'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/podcast/<int:podcast_id>')
def single_podcast(podcast_id):
    try:
        podcast = Podcast.query.get(podcast_id)
        if not podcast:
            abort(404)
        
        metadata = {
            'title': podcast.title,
            'description': podcast.description,
            'audio_url': podcast.audio_url,
            'duration': podcast.duration,
            'thumbnail': f"{request.url_root}static/images/podcast-thumbnail.jpg",
            'embed_url': f"{request.url_root}embed/{podcast.id}"
        }
        
        if hasattr(podcast, 'metadata'):
            podcast.metadata = json.dumps(metadata)
            db_session.commit()
        
        return render_template('single_podcast.html', podcast=podcast)
    except Exception as e:
        print(f"Error in single_podcast route: {e}")
        db_session.rollback()
        return "Error loading podcast", 500

@app.route('/embed/<int:podcast_id>')
def embed_podcast(podcast_id):
    try:
        podcast = Podcast.query.get(podcast_id)
        if not podcast:
            abort(404)
            
        response = make_response(render_template('embed.html', podcast=podcast))
        response.headers['X-Frame-Options'] = 'ALLOW-FROM https://www.linkedin.com'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://www.linkedin.com https://platform.linkedin.com"
        return response
    except Exception as e:
        print(f"Error in embed_podcast: {e}")
        return "Error loading podcast player", 500

@app.route('/views/<int:podcast_id>', methods=['POST'])
def increment_views(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    podcast.views += 1
    db_session.commit()
    return jsonify({'views': podcast.views})

@app.route('/podcast/<int:podcast_id>', methods=['DELETE'])
def delete_podcast(podcast_id):
    try:
        podcast = Podcast.query.get(podcast_id)
        if not podcast:
            return jsonify({'error': 'Podcast not found'}), 404
        
        # Delete from Cloudinary first
        if podcast.cloudinary_public_id:
            try:
                # Proper Cloudinary deletion with error handling
                delete_result = uploader.destroy(
                    podcast.cloudinary_public_id,
                    resource_type="video",  # Important: use video for audio files
                    invalidate=True  # Invalidate CDN cache
                )
                
                if delete_result.get('result') != 'ok':
                    print(f"Cloudinary delete warning: {delete_result}")
                    # Continue with database deletion even if Cloudinary fails
                
            except Exception as e:
                print(f"Cloudinary delete error: {e}")
                # Continue with database deletion even if Cloudinary fails
        
        # Delete from database
        db_session.delete(podcast)
        db_session.commit()
        
        return jsonify({'message': 'Podcast deleted successfully'}), 200
        
    except Exception as e:
        db_session.rollback()
        print(f"Error deleting podcast: {e}")
        return jsonify({'error': 'Failed to delete podcast'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Update init_db to include new column
def init_db():
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Add cloudinary_public_id column if it doesn't exist
        with engine.connect() as connection:
            connection.execute(text("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='podcasts' 
                        AND column_name='cloudinary_public_id'
                    ) THEN 
                        ALTER TABLE podcasts 
                        ADD COLUMN cloudinary_public_id VARCHAR(200);
                    END IF;
                END $$;
            """))
            connection.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    init_db()  # Initialize the database before running the app
    port = int(os.environ.get('PORT', 3030))
    app.run(host='0.0.0.0', port=port)