# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory
import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:PkiSFayTnRTkdMlwwmrLOINhrMfBlwdm@autorack.proxy.rlwy.net:58219/railway"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Database Models
class Podcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    audio_url = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Float)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

with app.app_context():
    db.create_all()

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
    podcast.likes += 1
    db.session.commit()
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
            
            db.session.add(podcast)
            db.session.commit()
            
            return jsonify(podcast.to_dict()), 200
        except Exception as e:
            print(f"Upload error: {str(e)}")
            return jsonify({'error': 'Upload failed'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

if __name__ == '__main__':
    app.run(debug=True)