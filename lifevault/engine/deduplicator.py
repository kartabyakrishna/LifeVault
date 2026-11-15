import os
import sqlite3
from typing import Tuple, List, Dict, Optional, Callable
from ..core.hasher import batch_compute_sha256

class DeduplicationEngine:
    """Multi-stage exact bit-for-bit duplicate finder and quarantine manager."""

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn

    def identify_exact_duplicates(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Tuple[int, int, int]:
        """Group identical files by size and SHA-256 hash.
        
        Returns (groups, duplicates, bytes_saved).
        """
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
        
        # 2. Gather candidate files that need hashing
        cur.execute("""
            SELECT id, source_path 
            FROM files 
            WHERE source_size IN (
                SELECT source_size 
                FROM files 
                WHERE source_size > 0 
                GROUP BY source_size 
                HAVING count(*) > 1
            ) AND source_sha256 IS NULL
        """)
        to_hash_rows = cur.fetchall()
        total_to_hash = len(to_hash_rows)
        
        if total_to_hash > 0:
            batch_size = 500
            for i in range(0, total_to_hash, batch_size):
                chunk = to_hash_rows[i:i + batch_size]
                path_to_id = {row[1]: row[0] for row in chunk if os.path.exists(row[1])}
                hashes = batch_compute_sha256(list(path_to_id.keys()))
                
                updates = [(h, path_to_id[p]) for p, h in hashes.items()]
                if updates:
                    cur.executemany("UPDATE files SET source_sha256 = ? WHERE id = ?", updates)
                    self.conn.commit()
                    
                if progress_callback:
                    progress_callback("Hashing collision candidates", min(i + len(chunk), total_to_hash), total_to_hash)

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
                saved_bytes += (d[2] or 0)
                
        self.conn.commit()
        return len(dupe_hashes), total_dupes, saved_bytes
