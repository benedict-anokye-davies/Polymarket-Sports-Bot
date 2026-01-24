"""
Script to fix database schema by adding missing username column.
"""
import sqlite3
import sys

def fix_database():
    try:
        conn = sqlite3.connect('polymarket_bot.db')
        cursor = conn.cursor()

        # Check if username column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'username' not in columns:
            print("Adding username column to users table...")
            # Add username column
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(50)")

            # Update existing users with a default username based on email
            cursor.execute("""
                UPDATE users
                SET username = SUBSTR(email, 1, INSTR(email, '@') - 1)
                WHERE username IS NULL
            """)

            conn.commit()
            print("[OK] Username column added successfully")
        else:
            print("[OK] Username column already exists")

        # Check for indexes
        cursor.execute("PRAGMA index_list(users)")
        indexes = [idx[1] for idx in cursor.fetchall()]

        if 'ix_users_username' not in indexes:
            print("Creating username index...")
            cursor.execute("CREATE UNIQUE INDEX ix_users_username ON users (username)")
            conn.commit()
            print("[OK] Username index created")
        else:
            print("[OK] Username index already exists")

        if 'ix_users_email' not in indexes:
            print("Creating email index...")
            cursor.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
            conn.commit()
            print("[OK] Email index created")
        else:
            print("[OK] Email index already exists")

        conn.close()
        print("\n[SUCCESS] Database schema fixed successfully!")
        return True

    except Exception as e:
        print(f"Error fixing database: {e}")
        return False

if __name__ == "__main__":
    success = fix_database()
    sys.exit(0 if success else 1)
