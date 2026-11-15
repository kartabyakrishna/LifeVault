import os
import re
import sqlite3
from ..core.filesystem import safe_ntfs_move, create_hardlink

class RefinementEngine:
    """Classifies primary files into YYYY/YYYY-MM structure and isolates duplicates into quarantine."""

    def __init__(self, db_conn: sqlite3.Connection, target_root: str, quarantine_root: str):
        self.conn = db_conn
        self.target_root = target_root
        self.quarantine_root = quarantine_root

    def resolve_target(self, row: sqlite3.Row) -> str:
        src = row['source_path']
        fname = row['source_name']
        is_dupe = row['is_duplicate']
        
        if is_dupe == 1:
            drive, rel = os.path.splitdrive(src)
            return os.path.join(self.quarantine_root, rel.lstrip('\\/'))
            
        parent = row['parent_folder'] or ''
        m_ym = re.search(r'[\\/](20\d{2})[-_\\/](20\d{2}-([01]\d))', parent)
        m_y = re.search(r'[\\/](20\d{2})(?:[\\/]|$)', parent)
        
        if m_ym:
            year, month = m_ym.group(1), m_ym.group(2)
        elif m_y:
            year = m_y.group(1)
            m_fn = re.search(r'(20\d{2})[-_]?([01]\d)', fname)
            month = f"{year}-{m_fn.group(2)}" if m_fn and m_fn.group(1) == year else f"{year}-General"
        else:
            d = row['capture_date'] or '2020-01-01'
            year, month = d[:4], d[:7]
            
        return os.path.join(self.target_root, year, month, fname)

    def execute(self, dry_run: bool = False):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM files WHERE status = 'PENDING'")
        rows = cur.fetchall()
        
        refined = 0
        quarantined = 0
        for r in rows:
            dst = self.resolve_target(r)
            if not dry_run:
                safe_ntfs_move(r['source_path'], dst)
                status = "QUARANTINED" if r['is_duplicate'] == 1 else "REFINED"
                cur.execute("UPDATE files SET target_path = ?, status = ? WHERE id = ?", (dst, status, r['id']))
            if r['is_duplicate'] == 1:
                quarantined += 1
            else:
                refined += 1
        if not dry_run:
            self.conn.commit()
        return refined, quarantined
