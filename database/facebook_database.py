import sqlite3
from src.config.config import Config
from src.utils.logger import app_logger

class FacebookDatabase:
    """Manages SQLite database for storing processed posts."""
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        """Connect to SQLite database."""
        Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(Config.DB_PATH)
        self.cursor = self.conn.cursor()

    def _create_table(self):
        """Create the processed_posts table."""
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS processed_posts (
            id TEXT PRIMARY KEY,
            date TEXT,
            page TEXT,
            success INTEGER
        );
        '''
        self._execute_query(create_table_sql)

    def _execute_query(self, query: str, params: tuple = ()):
        """Execute a query with error handling."""
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
        except sqlite3.Error as e:
            app_logger.error(f"SQLite error: {e}")
            self.conn.rollback()
            raise

    def post_exists(self, post_id: str) -> bool:
        """Check if a post exists in the database.
        
        Args:
            post_id: The ID of the post to check
            
        Returns:
            bool: True if post exists, False otherwise
        """
        query = 'SELECT 1 FROM processed_posts WHERE id = ?'
        try:
            self.cursor.execute(query, (post_id,))
            result = self.cursor.fetchone()
            return result is not None
        except sqlite3.Error as e:
            app_logger.error(f"Error checking if post {post_id} exists: {e}")
            return False

    def insert_post(self, post_id: str, date: str, page: str, success: int) -> bool:
        """Insert a post into the database."""
        query = 'INSERT INTO processed_posts (id, date, page, success) VALUES (?, ?, ?, ?)'
        try:
            self._execute_query(query, (post_id, date, page, success))
            return True
        except sqlite3.Error:
            app_logger.error(f"Post {post_id} already exists")
            return False

    def update_post_success(self, post_id: str, success: int) -> bool:
        """Update the success status of a post."""
        query = 'UPDATE processed_posts SET success = ? WHERE id = ?'
        try:
            self._execute_query(query, (success, post_id))
            return True
        except sqlite3.Error:
            app_logger.error(f"Failed to update post {post_id}")
            return False

    def close(self):
        """Close database connections."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()