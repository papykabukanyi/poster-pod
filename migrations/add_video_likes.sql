-- migrations/add_video_likes.sql
DO $$
BEGIN
    -- Add likes column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'videos' AND column_name = 'likes') THEN
        ALTER TABLE videos ADD COLUMN likes INTEGER DEFAULT 0;
    END IF;
END $$;