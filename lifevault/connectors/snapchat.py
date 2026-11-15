import json
import mimetypes
import os
from datetime import datetime, timezone
from typing import Any, Dict
from .base import BaseConnector
from ..core.hasher import compute_sha256, compute_perceptual_hashes

class SnapchatConnector(BaseConnector):
    source_id = "snapchat"
    category = "cloud_takeout"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        cnt = 0
        items = []

        memories_meta = {}
        mj = os.path.join(src_path, "json", "memories_history.json")
        if not os.path.exists(mj):
            mj = os.path.join(src_path, "memories_history.json")
        if os.path.exists(mj):
            try:
                with open(mj, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    for e in data.get("Saved Media", []):
                        d = e.get("Date")
                        if d:
                            memories_meta[d] = e
            except Exception:
                pass

        for r, _, fs in os.walk(src_path):
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext not in {".jpg", ".jpeg", ".mp4", ".mov", ".png"}:
                    continue
                mp = os.path.join(r, f)
                try:
                    sz = os.path.getsize(mp)
                    if sz == 0:
                        continue
                except OSError:
                    continue

                h = compute_sha256(mp)
                mime = mimetypes.guess_type(mp)[0] or "application/octet-stream"
                can_rel = os.path.relpath(mp, src_path)

                ph, dh = None, None
                if ext in {".jpg", ".jpeg", ".png"}:
                    ph, dh = compute_perceptual_hashes(mp)

                self.db.upsert_blob(h, sz, mime, ext, can_rel, ph, dh)

                mtime = os.path.getmtime(mp)
                ts_utc = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                itype = "video" if ext in {".mp4", ".mov"} else "photo"

                items.append({
                    "source_id": self.source_id,
                    "source_native_id": f"{can_rel}:{h[:12]}",
                    "item_type": itype,
                    "timestamp_utc": ts_utc,
                    "primary_blob_sha256": h,
                    "attributes_json": {"filename": f}
                })
                cnt += 1

        if items:
            self.db.batch_insert_timeline_items(items)
        return {"snapchat_items": cnt}
