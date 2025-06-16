# app.py
from flask import Flask, render_template, request, jsonify, abort, session, make_response, send_from_directory, url_for, redirect, session
import cloudinary
import cloudinary.uploader
import os
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    Text, 
    Float, 
    JSON,
    text,
    create_engine, 
    inspect
)
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
import json
from config import *
from cloudinary import uploader
from werkzeug.utils import secure_filename
from models.base import Base, db_session, engine
from models.news import NewsArticle
from services.news_service import NewsService
from services.image_service import ImageService
import secrets
import requests
import logging
from urllib.parse import urlencode
from services.twitter_service import TwitterService
import tweepy
from datetime import datetime, timedelta
import time
from services.scheduler_service import SchedulerService
from models.video import Video
import mimetypes
import tempfile

# Add allowed video types
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

# Add to existing ALLOWED_VIDEO_EXTENSIONS
ALLOWED_MIME_TYPES = {
    'video/mp4', 'video/quicktime', 'video/x-msvideo',
    'video/webm', 'video/x-matroska'
}

def allowed_video_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# Add after imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config')
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB

# Add session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_TYPE'] = 'filesystem'

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True,
    api_proxy='http://proxy.server:3128'  # Add this line if you're behind a proxy
)

# Timeago filter
def timeago(date):
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        except:
            return ''
    
    if not isinstance(date, datetime):
        return ''
        
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
    videos = Video.query.order_by(Video.created_at.desc()).all()
    podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
    return render_template('admin.html', podcasts=podcasts, videos=videos)

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
    print("Upload endpoint hit")
    
    if 'audio' not in request.files:
        print("No audio file in request")
        return jsonify({'error': 'No audio file uploaded'}), 400

    try:
        file = request.files['audio']
        title = request.form.get('title', '').strip()

        # Basic validation
        if not file or not file.filename:
            return jsonify({'error': 'No file selected'}), 400
            
        if not title:
            return jsonify({'error': 'Title is required'}), 400

        # File type check
        allowed_extensions = {'.mp3', '.wav', '.m4a'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

        # Upload to Cloudinary with resource info
        upload_result = uploader.upload(
            file,
            resource_type='video',  # Use 'video' for audio files
            folder='podcasts'
        )
        
        # Extract duration from Cloudinary response
        duration = upload_result.get('duration', 0)  # Duration in seconds
        
        # Save to database with duration
        podcast = Podcast(
            title=title,
            description=request.form.get('description', '').strip(),
            audio_url=upload_result['secure_url'],
            cloudinary_public_id=upload_result['public_id'],
            duration=duration  # Store duration in seconds
        )
        
        db_session.add(podcast)
        db_session.commit()

        return jsonify({'success': True, 'message': 'Upload successful'}), 200

    except Exception as e:
        print(f"Upload error: {e}")
        db_session.rollback()
        return jsonify({'error': str(e)}), 500

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
            response.headers['X-Frame-Options'] = 'ALLOW-FROM *'
            response.headers['Content-Security-Policy'] = "frame-ancestors 'self' *"
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

@app.route('/news')
def news_page():
    try:
        scheduler = SchedulerService()
        current_time = datetime.utcnow()
        next_update = scheduler.get_next_update()
        
        articles = NewsService.get_cached_news()
        
        all_articles = []
        if (articles.get('breaking')):
            all_articles.append(articles['breaking'])
        all_articles.extend(articles.get('other', []))
        
        preloaded_images = ImageService.preload_images(all_articles)
        
        return render_template(
            'news.html',
            breaking_news=articles.get('breaking'),
            other_news=articles.get('other', []),
            preloaded_images=preloaded_images,
            total_articles=len(all_articles),
            next_update=next_update.isoformat(),
            server_time=current_time.isoformat()
        )
    except Exception as e:
        logging.error(f"Error in news_page: {e}")
        current_time = datetime.utcnow()
        return render_template(
            'news.html',
            breaking_news=None,
            other_news=[],
            preloaded_images=[],
            total_articles=0,
            next_update=(current_time + timedelta(seconds=7200)).isoformat(),
            server_time=current_time.isoformat()
        )

@app.route('/static/images/default-news.jpg')
def default_news_image():
    # Return a default image for when news images fail to load
    return send_from_directory('static/images', 'default-news.jpg')

@app.route('/news/update-time')
def get_news_update_time():
    try:
        current_time = datetime.utcnow()
        
        # Initialize if needed
        if not NewsService.last_update_time:
            NewsService.last_update_time = current_time
            NewsService.next_update_time = current_time + timedelta(seconds=NewsService.breaking_news_check_interval)
            # Initial fetch
            NewsService.fetch_news(force_breaking=True)
        
        return jsonify({
            'last_update': NewsService.last_update_time.isoformat(),
            'next_update': NewsService.next_update_time.isoformat(),
            'server_time': current_time.isoformat()
        })
    except Exception as e:
        print(f"Error getting update time: {e}")
        current_time = datetime.utcnow()
        return jsonify({
            'last_update': current_time.isoformat(),
            'next_update': (current_time + timedelta(seconds=NewsService.breaking_news_check_interval)).isoformat(),
            'server_time': current_time.isoformat()
        })

@app.route('/news/refresh', methods=['GET'])
def refresh_news():
    try:
        NewsService.force_refresh()
        return jsonify({'status': 'success', 'message': 'News refreshed successfully'})
    except Exception as e:
        print(f"Error refreshing news: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/twitter-manager')
def twitter_manager():
    try:
        scheduler = SchedulerService.get_instance()
        twitter_service = scheduler.twitter_service
        current_time = datetime.utcnow()
        
        # Use cached connection status
        is_connected = twitter_service.check_connection()
        
        return render_template(
            'twitter_manager.html',
            is_connected=is_connected,
            next_twitter_post=scheduler.next_twitter_update.isoformat(),
            server_time=current_time.isoformat(),
            activity_logs=twitter_service.get_recent_logs(limit=10),
            hide_preloader=True
        )
    except Exception as e:
        logging.error(f"Twitter manager error: {e}")
        return render_template(
            'twitter_manager.html',
            is_connected=False,
            error=str(e),
            next_twitter_post=(datetime.utcnow() + timedelta(seconds=1800)).isoformat(),
            server_time=datetime.utcnow().isoformat(),
            hide_preloader=True
        )

@app.route('/twitter-auth')
def twitter_auth():
    """Twitter OAuth flow initialization"""
    try:
        twitter_service = TwitterService()
        auth_url = twitter_service.get_auth_url()
        return redirect(auth_url)
    except Exception as e:
        logging.error(f"Twitter auth error: {e}")
        return redirect(url_for('twitter_manager'))

@app.route('/postervideo')
def video_list():
    try:
        videos = Video.query.order_by(Video.created_at.desc()).all()
        return render_template('postervideo.html', videos=videos)
    except Exception as e:
        logging.error(f"Error loading videos: {e}")
        return "Error loading videos", 500

@app.route('/video/<slug>')
def video_player(slug):
    try:
        video = Video.query.filter_by(slug=slug).first()
        if not video:
            abort(404)
            
        # Increment views
        video.views += 1
        
        # Get recommended videos
        recommended = Video.query.filter(
            Video.id != video.id
        ).order_by(Video.views.desc()).limit(5).all()
        
        # Convert datetime to string for template
        for rec in recommended:
            if isinstance(rec.created_at, datetime):
                rec.created_at_str = rec.created_at.isoformat()
        
        db_session.commit()
        
        return render_template(
            'video_player.html', 
            video=video,
            recommended=recommended
        )
    except Exception as e:
        logging.error(f"Error loading video player: {e}")
        db_session.rollback()
        return "Error loading video", 500

@app.route('/api/search_videos')
def search_videos():
    query = request.args.get('q', '').strip()
    try:
        if (query):
            videos = Video.query.filter(
                Video.title.ilike(f'%{query}%')
            ).limit(5).all()
            return jsonify([video.to_dict() for video in videos])
        return jsonify([])
    except Exception as e:
        logging.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload/video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded'}), 400
        
    try:
        video_file = request.files['video']
        thumbnail_file = request.files['thumbnail']
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        # Validation
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not video_file or not video_file.filename:
            return jsonify({'error': 'Video file is required'}), 400
        if not thumbnail_file or not thumbnail_file.filename:
            return jsonify({'error': 'Thumbnail is required'}), 400

        # Check file size
        max_video_size = 500 * 1024 * 1024  # 500MB
        if video_file.content_length > max_video_size:
            return jsonify({
                'error': f'Video file too large. Maximum size is {max_video_size/1024/1024}MB'
            }), 400

        # Upload video
        try:
            video_data = video_file.read()
            video_result = uploader.upload(
                video_data,
                resource_type='video',
                folder='videos',
                eager=[
                    {'quality': 'auto', 'format': 'mp4'},
                    {'width': 720, 'crop': 'scale', 'quality': 'auto'}
                ]
            )
        except Exception as e:
            return jsonify({
                'error': f'Video upload failed: {str(e)}'
            }), 500

        # Upload thumbnail
        try:
            thumbnail_data = thumbnail_file.read()
            thumb_result = uploader.upload(
                thumbnail_data,
                folder='video_thumbnails',
                transformation=[
                    {'width': 720, 'crop': 'fill'},
                    {'quality': 'auto'}
                ]
            )
        except Exception as e:
            return jsonify({
                'error': f'Thumbnail upload failed: {str(e)}'
            }), 500

        # Create video record
        video = Video(
            title=title,
            description=description,
            video_url=video_result['secure_url'],
            thumbnail_url=thumb_result['secure_url'],
            duration=video_result.get('duration', 0),
            cloudinary_public_id=video_result['public_id']
        )
        
        db_session.add(video)
        db_session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully',
            'video': video.to_dict()
        }), 200

    except Exception as e:
        logging.error(f"Video upload error: {str(e)}")
        db_session.rollback()
        return jsonify({
            'error': f'Video upload failed: {str(e)}'
        }), 500

@app.route('/video/<slug>/like', methods=['POST'])
def like_video(slug):
    try:
        video = Video.query.filter_by(slug=slug).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Check if user already liked this video in this session
        session_likes = session.get('video_likes', {})
        if str(video.id) in session_likes:
            return jsonify({'error': 'Already liked', 'likes': video.likes}), 400
        
        video.likes += 1
        session_likes[str(video.id)] = True
        session['video_likes'] = session_likes
        
        db_session.commit()
        return jsonify({'success': True, 'likes': video.likes}), 200
    except Exception as e:
        logging.error(f"Error liking video: {str(e)}")
        db_session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/video/<slug>/comment', methods=['POST'])
def add_comment(slug):
    try:
        video = Video.query.filter_by(slug=slug).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Check if user already commented on this video in this session
        session_comments = session.get('video_comments', {})
        if str(video.id) in session_comments:
            return jsonify({'error': 'Already commented on this video'}), 400
            
        comment_text = request.form.get('text', '').strip()
        if not comment_text:
            return jsonify({'error': 'Comment text is required'}), 400
            
        comment_data = {
            'id': secrets.token_hex(8),
            'user': request.form.get('user', 'Anonymous'),
            'text': comment_text,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if not video.comments:
            video.comments = []
            
        video.comments.append(comment_data)
        session_comments[str(video.id)] = True
        session['video_comments'] = session_comments
        
        db_session.commit()
        return jsonify({'success': True, 'comment': comment_data}), 200
        
    except Exception as e:
        logging.error(f"Error adding comment: {str(e)}")
        db_session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/video/<slug>/view', methods=['POST'])
def record_view(slug):
    try:
        video = Video.query.filter_by(slug=slug).first()
        if not video:
            return jsonify({'error': 'Video not found'}), 404
            
        # Create unique session key for this video view
        session_id = session.get('session_id')
        if not session_id:
            session_id = secrets.token_hex(16)
            session['session_id'] = session_id
            
        view_key = f'video_view_{video.id}_{session_id}'
        
        # Check if completed flag exists
        if not session.get(view_key + '_completed'):
            video.views += 1
            db_session.commit()
            session[view_key + '_completed'] = True
            
        return jsonify({'success': True, 'views': video.views}), 200
    except Exception as e:
        db_session.rollback()
        return jsonify({'error': str(e)}), 500

def run_migration():
    """Run database migrations"""
    try:
        with engine.connect() as connection:
            # Create pgcrypto extension if not exists
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            
            # Execute existing migrations
            with open('migrations/alter_news_articles.sql') as f:
                connection.execute(text(f.read()))
            
            # Execute videos table migration
            with open('migrations/add_videos_table.sql') as f:
                connection.execute(text(f.read()))
                
            # Execute video slugs migration
            with open('migrations/add_video_slugs.sql') as f:
                connection.execute(text(f.read()))

            # Execute video likes migration
            with open('migrations/add_video_likes.sql') as f:
                connection.execute(text(f.read()))
                
            connection.commit()
        print("Migrations completed successfully")
    except Exception as e:
        print(f"Migration error: {e}")

# Update init_db function
def init_db():
    inspector = inspect(engine)
    try:
        Base.metadata.create_all(bind=engine)
        run_migration()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 100MB'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error. Please try again later'}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

def init_app(app):
    try:
        with app.app_context():
            print("Initializing database...")
            init_db()
            print("Starting scheduler...")
            scheduler = SchedulerService.get_instance()
            scheduler.start()
            print("Initialization complete")
            return True
    except Exception as e:
        print(f"Error during app initialization: {e}")
        # Don't fail completely, let the app start anyway
        return False

if __name__ == '__main__':
    init_app(app)
    app.run(debug=True)