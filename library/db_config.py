
import mysql.connector
from mysql.connector import pooling, Error
from contextlib import contextmanager
import hashlib

class Database:
    _pool = None
    
    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            try:
                config = {
                    'host': 'localhost',
                    'database': 'library_management_system',
                    'user': 'root',
                    'password': 'mysql',  
                    'pool_name': 'library_pool',
                    'pool_size': 10,
                    'autocommit': False
                }
                
                cls._pool = pooling.MySQLConnectionPool(**config)
                print("✅ Database connection pool created successfully")
                
            except Error as e:
                print(f"❌ Error creating connection pool: {e}")
                cls._pool = None
                
        return cls._pool
    
    @classmethod
    @contextmanager
    def get_connection(cls):
        pool = cls.get_pool()
        if pool is None:
            raise Exception("No database connection pool available")
        
        connection = pool.get_connection()
        try:
            yield connection
        finally:
            connection.close()

class AuthHelper:
    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return AuthHelper.hash_password(plain_password) == hashed_password