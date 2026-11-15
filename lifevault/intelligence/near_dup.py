import json
from typing import Dict, List, Tuple
from ..core.db import ManifestDatabase
from ..core.hasher import hamming_distance

class NearDuplicateMatcher:
    def __init__(self, db: ManifestDatabase):
        self.db = db

    def link_perceptual_duplicates(self, max_dist: int = 8) -> int:
        with self.db.get_connection() as c:
            rows = c.execute(
                """
                SELECT t.id, t.timestamp_utc, b.sha256, b.phash
                FROM timeline_items t
                JOIN blobs b ON t.primary_blob_sha256 = b.sha256
                WHERE b.phash IS NOT NULL
                ORDER BY t.timestamp_utc ASC
                """
            ).fetchall()

        n = len(rows)
        linked = 0
        for i in range(n):
            for j in range(i + 1, n):
                ph1 = rows[i]["phash"]
                ph2 = rows[j]["phash"]
                dist = hamming_distance(ph1, ph2)
                if dist <= max_dist:
                    conf = max(0.0, 1.0 - (dist / 64.0))
                    status = "auto_verified" if dist <= 4 else "pending"
                    ev = {"hamming_distance": dist, "phash_a": ph1, "phash_b": ph2}
                    self.db.link_items(rows[i]["id"], rows[j]["id"], "near_dup_phash", conf, status, ev)
                    linked += 1
        return linked
