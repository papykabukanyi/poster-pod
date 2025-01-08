from sqlalchemy import create_engine, text
from config import SQLALCHEMY_DATABASE_URI

def migrate_database():
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    with engine.connect() as connection:
        # Add views column if it doesn't exist
        try:
            connection.execute(text("""
                ALTER TABLE podcasts 
                ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0;
            """))
            # Add metadata column for social embeds
            connection.execute(text("""
                ALTER TABLE podcasts 
                ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
            """))
            connection.commit()
            print("Successfully added views and metadata columns")
        except Exception as e:
            print(f"Error adding columns: {e}")
            connection.rollback()

if __name__ == "__main__":
    migrate_database()