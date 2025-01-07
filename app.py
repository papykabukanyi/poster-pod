from flask import Flask, render_template, request, jsonify, send_from_directory
import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Store podcasts in memory (in production, use a database)
podcasts = []

@app.route('/')
def index():
    return render_template('index.html', podcasts=podcasts)

@app.route('/admin')
def admin():
    return render_template('admin.html', podcasts=podcasts)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/upload', methods=['POST'])
def upload_podcast():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    file = request.files['audio']
    title = request.form.get('title', 'Untitled Podcast')
    description = request.form.get('description', '')
    
    if file:
        try:
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file,
                resource_type="auto",
                folder="podcasts/",
                format="mp3"
            )
            
            # Store podcast info
            podcast = {
                'title': title,
                'description': description,
                'url': result['secure_url'],
                'duration': result.get('duration', 0)
            }
            podcasts.append(podcast)
            
            return jsonify(podcast), 200
        except Exception as e:
            print(f"Upload error: {str(e)}")
            return jsonify({'error': 'Upload failed'}), 500
    
    return jsonify({'error': 'Invalid file'}), 400

if __name__ == '__main__':
    app.run(debug=True)