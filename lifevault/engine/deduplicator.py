import os
import sqlite3
from typing import Tuple, List, Dict
from ..core.hasher import compute_sha256

class DeduplicationEngine:
    """Multi-stage exact bit-for-bit duplicate finder and quarantine manager."""

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn

    def identify_exact_duplicates(self) -> Tuple[int, int, int]:
        """Group identical files by size and SHA-256 hash. Returns (groups, duplicates, bytes_saved)."""
        cur = self.conn.cursor()
        
        # 1. Find candidates with same size
        cur.execute("""
            SELECT source_size, count(*) 
            FROM files 
            WHERE source_size > 0 
            GROUP BY source_size 
            HAVING count(*) > 1
        """)
        size_groups = cur.fetchall()
        
        # 2. Hash candidates
        for row in size_groups:
            sz = row[0]
            cur.execute("SELECT id, source_path FROM files WHERE source_size = ? AND source_sha256 IS NULL", (sz,))
            to_hash = cur.fetchall()
            for fid, fpath in to_hash:
                if os.path.exists(fpath):
                    h = compute_sha256(fpath)
                    cur.execute("UPDATE files SET source_sha256 = ? WHERE id = ?", (h, fid))
            self.conn.commit()

        # 3. Mark duplicate groups
        cur.execute("""
            SELECT source_sha256, count(*) 
            FROM files 
            WHERE source_sha256 IS NOT NULL 
            GROUP BY source_sha256 
            HAVING count(*) > 1
        """)
        dupe_hashes = cur.fetchall()
        
        group_id = 0
        total_dupes = 0
        saved_bytes = 0

        for r in dupe_hashes:
            h = r[0]
            cur.execute("SELECT id, source_path, source_size FROM files WHERE source_sha256 = ? ORDER BY id ASC", (h,))
            members = cur.fetchall()
            primary = members[0]
            primary_id = primary[0]
            group_id += 1
            
            for d in members[1:]:
                dupe_id = d[0]
                cur.execute("""
                    UPDATE files 
                    SET is_duplicate = 1, primary_id = ?, duplicate_group = ? 
                    WHERE id = ?
                """, (primary_id, group_id, dupe_id))
                total_dupes += 1
                saved_bytes += d[2]
                
        self.conn.commit()
        return len(dupe_hashes), total_dupes, saved_bytes
