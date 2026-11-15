import mimetypes
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict
from .base import BaseConnector
from ..core.hasher import compute_sha256, compute_perceptual_hashes

DCIM_EXTS = {
    ".jpg", ".jpeg", ".png", ".heic", ".webp",
    ".arw", ".nef", ".cr2", ".cr3", ".dng", ".raw",
    ".mp4", ".mov", ".avi", ".mkv", ".3gp"
}

def extract_date_from_name(fname: str) -> str:
    m = re.search(r'(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?:[-_]?([0-2]\d)([0-5]\d)([0-5]\d)?)?', fname)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        h = m.group(4) or "12"
        mi = m.group(5) or "00"
        s = m.group(6) or "00"
        try:
            return datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return None

class DcimConnector(BaseConnector):
    source_id = "camera_dcim"
    category = "camera"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        cnt = 0
        items = []

        for r, _, fs in os.walk(src_path):
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext not in DCIM_EXTS:
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
                if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                    ph, dh = compute_perceptual_hashes(mp)

                self.db.upsert_blob(h, sz, mime, ext, can_rel, ph, dh)

                ts_utc = extract_date_from_name(f)
                if not ts_utc:
                    mtime = os.path.getmtime(mp)
                    ts_utc = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

                itype = "video" if ext in {".mp4", ".mov", ".avi", ".mkv", ".3gp"} else "photo"
                items.append({
                    "source_id": self.source_id,
                    "source_native_id": f"{can_rel}:{h[:12]}",
                    "item_type": itype,
                    "timestamp_utc": ts_utc,
                    "primary_blob_sha256": h,
                    "attributes_json": {"filename": f, "ext": ext}
                })
                cnt += 1
                if len(items) >= 2000:
                    self.db.batch_insert_timeline_items(items)
                    items = []

        if items:
            self.db.batch_insert_timeline_items(items)
        return {"media_items": cnt}
