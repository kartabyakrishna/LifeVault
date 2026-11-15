import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from .base import BaseConnector
from ..core.hasher import compute_sha256

AUDIO_EXTS = {".m4a", ".mp3", ".amr", ".wav", ".aac", ".ogg", ".3gp", ".opus"}

def parse_call_filename(fname: str) -> Tuple[Optional[str], Optional[str]]:
    b = os.path.splitext(fname)[0]
    p_num = None
    m_p = re.search(r'\(([\d\+\s\-]+)\)', b)
    if m_p:
        p_num = re.sub(r'[\s\-]', '', m_p.group(1))
    else:
        m_w = re.search(r'(?:with|to|from)\s+([A-Za-z0-9_\s]+?)(?:[-_]\d|\(|$)', b, re.IGNORECASE)
        if m_w:
            p_num = m_w.group(1).strip()

    ts_s = None
    m_dt = re.search(r'(?:^|[\s_])(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?:[-_]?([0-2]\d)([0-5]\d)([0-5]\d)?)?', b)
    if m_dt:
        y, mo, d = m_dt.group(1), m_dt.group(2), m_dt.group(3)
        h = m_dt.group(4) or "12"
        mi = m_dt.group(5) or "00"
        s = m_dt.group(6) or "00"
        try:
            dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), tzinfo=timezone.utc)
            ts_s = dt.isoformat()
        except ValueError:
            pass
    return p_num, ts_s

class AudioCallsConnector(BaseConnector):
    source_id = "cubecall"
    category = "voice_recorder"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        cnt = 0
        items = []
        entity_links = []

        for r, _, fs in os.walk(src_path):
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext not in AUDIO_EXTS:
                    continue
                mp = os.path.join(r, f)
                try:
                    sz = os.path.getsize(mp)
                    if sz == 0:
                        continue
                except OSError:
                    continue

                h = compute_sha256(mp)
                mime = mimetypes.guess_type(mp)[0] or "audio/mp4"
                can_rel = os.path.relpath(mp, src_path)

                self.db.upsert_blob(h, sz, mime, ext, can_rel)

                caller, ts_utc = parse_call_filename(f)
                if not ts_utc:
                    mtime = os.path.getmtime(mp)
                    ts_utc = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

                attr = {"caller_raw": caller, "filename": f}
                iid = str(uuid.uuid4())

                items.append({
                    "id": iid,
                    "source_id": self.source_id,
                    "source_native_id": f"{can_rel}:{h[:12]}",
                    "item_type": "call_audio",
                    "timestamp_utc": ts_utc,
                    "primary_blob_sha256": h,
                    "summary_text": f"Call with {caller}" if caller else "Call recording",
                    "attributes_json": attr
                })

                if caller:
                    eid = f"ent_{re.sub(r'[^a-zA-Z0-9]', '_', caller).lower()}"
                    entity_links.append((iid, eid, caller))

                cnt += 1

        if items:
            self.db.batch_insert_timeline_items(items)

        if entity_links:
            with self.db.get_connection() as c:
                for iid, eid, caller in entity_links:
                    c.execute(
                        "INSERT OR IGNORE INTO entities (id, entity_type, canonical_name) VALUES (?, ?, ?)",
                        (eid, "person", caller)
                    )
                    c.execute(
                        "INSERT OR REPLACE INTO item_entities (item_id, entity_id, role) VALUES (?, ?, ?)",
                        (iid, eid, "caller")
                    )

        return {"calls_indexed": cnt}
