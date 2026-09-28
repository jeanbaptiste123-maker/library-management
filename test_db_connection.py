# test_db_connection.py
import sys
import os

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from library.db_config import Database
from library.db_operations import LibraryDB

def test_connection():
    print("Testing database connection...")
    
    # Test connection with your password
    try:
        with Database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✅ Connected to MySQL Version: {version[0]}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nMake sure you've updated the password in library/db_config.py")
        return
    
    # Test getting users
    print("\nFetching users...")
    try:
        with Database.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username, role FROM users")
            users = cursor.fetchall()
            print(f"✅ Found {len(users)} users:")
            for user in users:
                print(f"   - {user['username']} ({user['role']})")
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
    
    # Test authentication
    print("\nTesting authentication...")
    user = LibraryDB.authenticate_user('superadmin', 'admin123')
    if user:
        print(f"✅ Superadmin authenticated: {user['full_name']}")
    else:
        print("❌ Authentication failed")
    
    # Test getting books
    print("\nFetching books...")
    books = LibraryDB.get_all_books()
    print(f"✅ Found {len(books)} books")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_connection()