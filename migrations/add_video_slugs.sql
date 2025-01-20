-- migrations/add_video_slugs.sql
DO $$
BEGIN
    -- Add slug column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'videos' AND column_name = 'slug') THEN
        ALTER TABLE videos ADD COLUMN slug VARCHAR(16);
        
        -- Update existing rows with random slugs using substr of uuid
        UPDATE videos 
        SET slug = SUBSTR(REPLACE(gen_random_uuid()::text, '-', ''), 1, 16) 
        WHERE slug IS NULL;
        
        -- Add unique constraint and not null constraint
        ALTER TABLE videos ALTER COLUMN slug SET NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS videos_slug_idx ON videos(slug);
    END IF;
END $$;