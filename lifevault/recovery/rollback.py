import os
import sqlite3
import shutil

class RollbackEngine:
    """Restores all refined and quarantined files back to their exact original source paths."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def rollback(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM files WHERE status IN ('REFINED', 'QUARANTINED')")
        rows = cur.fetchall()
        
        restored = 0
        failed = 0
        for r in rows:
            target = r['target_path']
            source = r['source_path']
            if target and os.path.exists(target):
                try:
                    os.makedirs(os.path.dirname(source), exist_ok=True)
                    os.replace(target, source)
                    cur.execute("UPDATE files SET status = 'RESTORED' WHERE id = ?", (r['id'],))
                    restored += 1
                except Exception:
                    failed += 1
        conn.commit()
        conn.close()
        return {"restored": restored, "failed": failed}
