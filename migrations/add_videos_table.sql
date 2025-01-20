-- migrations/add_videos_table.sql
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,  
    description TEXT,
    video_url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    duration FLOAT,
    views INTEGER DEFAULT 0,
    cloudinary_public_id VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comments JSON DEFAULT '[]'::json
);