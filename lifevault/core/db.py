import sqlite3
import os
from typing import Optional, List, Dict, Any

class ManifestDatabase:
    """SQLite WAL-mode manifest database for tracking file inventory, refinement, and duplicates."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT UNIQUE,
                    source_name TEXT,
                    source_ext TEXT,
                    source_size INTEGER,
                    source_mtime REAL,
                    source_sha256 TEXT,
                    origin_root TEXT,
                    album_tag TEXT,
                    extra_tags TEXT,
                    capture_date TEXT,
                    target_dir TEXT,
                    target_path TEXT,
                    status TEXT DEFAULT 'PENDING',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_duplicate INTEGER DEFAULT 0,
                    primary_id INTEGER,
                    duplicate_group INTEGER,
                    parent_folder TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(source_sha256);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(source_size);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);")
