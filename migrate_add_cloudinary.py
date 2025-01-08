# migrate_add_cloudinary.py
from sqlalchemy import create_engine, text
from config import SQLALCHEMY_DATABASE_URI

def migrate_database():
    engine = create_engine(SQLALCHEMY_DATABASE_URI)
    with engine.connect() as connection:
        # Add cloudinary_public_id column if it doesn't exist
        try:
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
            print("Successfully added cloudinary_public_id column")
        except Exception as e:
            print(f"Error adding column: {e}")
            connection.rollback()

if __name__ == "__main__":
    migrate_database()