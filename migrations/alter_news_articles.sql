-- Drop existing table
DROP TABLE IF EXISTS news_articles;

-- Recreate with new schema
CREATE TABLE news_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    url TEXT,
    image_url TEXT,
    published_at TIMESTAMP WITHOUT TIME ZONE,
    source VARCHAR(100),
    category VARCHAR(50),
    is_breaking BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);