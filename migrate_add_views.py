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
            connection.commit()
            print("Successfully added views column")
        except Exception as e:
            print(f"Error adding views column: {e}")
            connection.rollback()

if __name__ == "__main__":
    migrate_database()