import json
import os
import mimetypes
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .base import BaseConnector
from ..core.hasher import compute_sha256, compute_perceptual_hashes

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tiff", ".tif",
    ".arw", ".nef", ".cr2", ".cr3", ".dng", ".raw",
    ".mp4", ".mov", ".avi", ".mkv", ".3gp", ".m4v", ".wmv"
}

def find_sidecar_json(media_p: str) -> Optional[str]:
    d = os.path.dirname(media_p)
    b = os.path.basename(media_p)
    cands = [
        f"{media_p}.json",
        f"{media_p}.supplemental-metadata.json",
        os.path.join(d, f"{b}.json"),
        os.path.join(d, f"{os.path.splitext(b)[0]}.json")
    ]
    if "(" in b and ")" in b:
        root, ext = os.path.splitext(b)
        idx = root[root.rfind("("):root.rfind(")") + 1]
        raw_root = root.replace(idx, "")
        cands.append(os.path.join(d, f"{raw_root}{ext}{idx}.json"))
    for c in cands:
        if os.path.exists(c):
            return c
    return None

class GoogleTakeoutConnector(BaseConnector):
    source_id = "google_takeout"
    category = "cloud_takeout"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        cnt = 0
        items = []

        for r, _, fs in os.walk(src_path):
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext not in MEDIA_EXTS:
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
                if ext in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
                    ph, dh = compute_perceptual_hashes(mp)

                self.db.upsert_blob(h, sz, mime, ext, can_rel, ph, dh)

                ts_utc = None
                lat, lon = None, None
                geo_src = None
                attr: Dict[str, Any] = {}

                sidecar = find_sidecar_json(mp)
                if sidecar:
                    try:
                        with open(sidecar, "r", encoding="utf-8", errors="ignore") as jf:
                            sdata = json.load(jf)
                        attr["takeout_sidecar"] = sdata
                        pt = sdata.get("photoTakenTime", {}).get("timestamp")
                        if pt:
                            ts_utc = datetime.fromtimestamp(int(pt), tz=timezone.utc).isoformat()
                        gd = sdata.get("geoData", {})
                        if gd.get("latitude") or gd.get("longitude"):
                            lat = float(gd.get("latitude", 0.0))
                            lon = float(gd.get("longitude", 0.0))
                            if lat != 0.0 or lon != 0.0:
                                geo_src = "takeout_json"
                    except Exception:
                        pass

                if not ts_utc:
                    mtime = os.path.getmtime(mp)
                    ts_utc = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

                itype = "video" if ext in {".mp4", ".mov", ".mkv", ".3gp"} else "photo"
                items.append({
                    "source_id": self.source_id,
                    "source_native_id": f"{can_rel}:{h[:12]}",
                    "item_type": itype,
                    "timestamp_utc": ts_utc,
                    "lat": lat,
                    "lon": lon,
                    "geo_source": geo_src,
                    "primary_blob_sha256": h,
                    "attributes_json": attr
                })
                cnt += 1

        if items:
            self.db.batch_insert_timeline_items(items)
        return {"media_items": cnt}
