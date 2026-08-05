import psycopg2
from app.core.config import settings

def get_db_connection():
    return psycopg2.connect(settings.DATABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # We don't wipe tables anymore to preserve users across reloads
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                size INTEGER NOT NULL,
                summary TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, filename)
            )
        """)
        conn.commit()
        
        # Add summary column if it doesn't exist (for existing tables)
        try:
            cursor.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT")
            conn.commit()
        except Exception:
            conn.rollback()
            
        cursor.close()
        conn.close()
        print("[INFO] Verified Postgres tables for multi-tenancy.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize DB schemas: {e}")
