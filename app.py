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
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB limit

# Initialize SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URI)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
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
        # Add MIME types validation
        allowed_extensions = {'.mp3', '.wav', '.m4a'}
        podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
        return render_template('admin.html', podcasts=podcasts, allowed_extensions=allowed_extensions)
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
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file uploaded'}), 400
        
        file = request.files['audio']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
            
        title = request.form.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
            
        description = request.form.get('description', '').strip()
        timestamp = request.form.get('timestamp')
        
        # Validate file type
        allowed_extensions = {'.mp3', '.wav', '.m4a'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Only MP3, WAV, and M4A files are allowed'}), 400
        
        upload_key = f"upload_{title}_{timestamp}"
        if upload_key in session:
            return jsonify({'error': 'Duplicate upload detected'}), 400
        
        session[upload_key] = True
        
        try:
            # Generate unique ID
            unique_id = f"podcast_{int(datetime.utcnow().timestamp())}_{os.urandom(8).hex()}"
            
            # Upload to Cloudinary
            upload_result = uploader.upload(
                file,
                resource_type="video",  # Use video type for audio files
                folder="podcasts/",
                public_id=unique_id,
                overwrite=True,
                unique_filename=True,
                chunk_size=20000000,  # 20MB chunks for large files
                timeout=120,  # Increased timeout for large files
                eager=[  # Add transcoding options
                    {"raw_convert": "mp3", "quality": "70"}
                ]
            )
            
            if not upload_result or 'secure_url' not in upload_result:
                raise Exception("Cloudinary upload failed")
            
            # Create new podcast
            podcast = Podcast(
                title=title,
                description=description,
                audio_url=upload_result['secure_url'],
                duration=upload_result.get('duration', 0),
                cloudinary_public_id=upload_result['public_id'],
                views=0,
                likes=0,
                created_at=datetime.utcnow()
            )
            
            db_session.add(podcast)
            db_session.commit()
            
            session.pop(upload_key, None)
            
            return jsonify({
                'success': True,
                'message': 'Upload successful',
                'podcast': podcast.to_dict()
            }), 200
            
        except Exception as e:
            if 'upload_result' in locals() and upload_result.get('public_id'):
                try:
                    uploader.destroy(upload_result['public_id'], resource_type="video")
                except Exception as ce:
                    print(f"Cloudinary cleanup error: {ce}")
            raise e
            
    except Exception as e:
        db_session.rollback()
        if 'upload_key' in locals():
            session.pop(upload_key, None)
        print(f"Upload error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Upload failed. Please try again.'
        }), 500

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
    try:
        # Use get() instead of get_or_404()
        podcast = Podcast.query.get(podcast_id)
        if not podcast:
            return jsonify({'error': 'Podcast not found'}), 404
            
        podcast.views += 1
        db_session.commit()
        return jsonify({'views': podcast.views})
    except Exception as e:
        db_session.rollback()
        print(f"Error incrementing views: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 100MB'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error. Please try again later'}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    init_db()  # Initialize the database before running the app
    port = int(os.environ.get('PORT', 3030))
    app.run(host='0.0.0.0', port=port)