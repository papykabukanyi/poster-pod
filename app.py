from flask import Flask, render_template, request, jsonify, abort, session
import cloudinary
import cloudinary.uploader
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from datetime import datetime
from config import *

# Initialize Flask app
app = Flask(__name__)

# Load configuration
app.config.from_object('config')
# Set a secret key for session management
app.secret_key = os.urandom(24)

# Initialize SQLAlchemy with the new style
engine = create_engine(SQLALCHEMY_DATABASE_URI)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

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

# Register the filter with Jinja2 after app initialization
app.jinja_env.filters['timeago'] = timeago

# Database Models
class Podcast(Base):
    __tablename__ = 'podcasts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    audio_url = Column(String(500), nullable=False)
    duration = Column(Float)
    likes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'audio_url': self.audio_url,
            'duration': self.duration,
            'likes': self.likes,
            'created_at': self.created_at.isoformat()
        }

def init_db():
    # Import all modules here that might define models
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route('/')
def index():
    podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
    return render_template('index.html', podcasts=podcasts)

@app.route('/admin')
def admin():
    podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
    return render_template('admin.html', podcasts=podcasts)

@app.route('/like/<int:podcast_id>', methods=['POST'])
def like_podcast(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    
    # Check if user has already liked this podcast
    session_likes = session.get('likes', {})
    if str(podcast_id) in session_likes:
        return jsonify({'error': 'Already liked'}), 400
    
    podcast.likes += 1
    session_likes[str(podcast_id)] = True
    session['likes'] = session_likes
    
    db_session.commit()
    return jsonify({'likes': podcast.likes})

@app.route('/upload', methods=['POST'])
def upload_podcast():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    file = request.files['audio']
    title = request.form.get('title', 'Untitled Podcast')
    description = request.form.get('description', '')
    
    if file and file.filename.endswith(('.mp3', '.wav')):
        try:
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file,
                resource_type="auto",
                folder="podcasts/",
                format="mp3"
            )
            
            # Create new podcast entry
            podcast = Podcast(
                title=title,
                description=description,
                audio_url=result['secure_url'],
                duration=result.get('duration', 0)
            )
            
            db_session.add(podcast)
            db_session.commit()
            
            return jsonify(podcast.to_dict()), 200
        except Exception as e:
            print(f"Upload error: {str(e)}")
            return jsonify({'error': 'Upload failed'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/podcast/<int:podcast_id>')
def single_podcast(podcast_id):
    podcast = db_session.query(Podcast).get(podcast_id)
    if podcast is None:
        abort(404)
    return render_template('single_podcast.html', podcast=podcast)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    init_db()  # Initialize the database before running the app
    port = int(os.environ.get('PORT', 3030))
    app.run(host='0.0.0.0', port=port)