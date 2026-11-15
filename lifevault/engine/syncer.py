import os
import shutil
import time
import sqlite3

class IncrementalSyncEngine:
    """Synchronizes source directories to backup drives incrementally with SQLite logging."""

    def __init__(self, src_dir: str, dst_dir: str, audit_db_path: str):
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.audit_db_path = audit_db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.audit_db_path)), exist_ok=True)
        with sqlite3.connect(self.audit_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    files_synced INTEGER,
                    bytes_synced INTEGER,
                    status TEXT
                )
            """)

    def sync(self) -> dict:
        copied = 0
        copied_bytes = 0
        errors = 0
        
        for root, _, files in os.walk(self.src_dir):
            for f in files:
                src_p = os.path.join(root, f)
                rel = os.path.relpath(src_p, self.src_dir)
                dst_p = os.path.join(self.dst_dir, rel)
                
                try:
                    sz = os.path.getsize(src_p)
                    if not os.path.exists(dst_p) or os.path.getsize(dst_p) != sz:
                        os.makedirs(os.path.dirname(dst_p), exist_ok=True)
                        shutil.copy2(src_p, dst_p)
                        copied += 1
                        copied_bytes += sz
                except Exception:
                    errors += 1
                    
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        status = "SUCCESS" if errors == 0 else f"ERRORS: {errors}"
        with sqlite3.connect(self.audit_db_path) as conn:
            conn.execute(
                "INSERT INTO sync_history (timestamp, files_synced, bytes_synced, status) VALUES (?, ?, ?, ?)",
                (ts, copied, copied_bytes, status)
            )
            
        return {"files_copied": copied, "bytes_copied": copied_bytes, "errors": errors, "status": status}
