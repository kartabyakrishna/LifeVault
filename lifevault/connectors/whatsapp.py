import mimetypes
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from .base import BaseConnector
from ..core.hasher import compute_sha256, compute_perceptual_hashes

def parse_whatsapp_txt_line(line: str) -> Optional[Tuple[str, str, str]]:
    m1 = re.match(r'^\[?(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\]?\s*[-:]?\s*([^:]+?):\s*(.*)$', line)
    if m1:
        d_str, t_str, sender, msg = m1.groups()
        return f"{d_str} {t_str}", sender.strip(), msg.strip()
    return None

def parse_txt_timestamp(ts_raw: str) -> str:
    fmts = [
        "%d/%m/%y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%d/%m/%y %I:%M %p", "%d/%m/%Y %I:%M %p",
        "%m/%d/%y %I:%M %p", "%m/%d/%Y %I:%M %p",
        "%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(ts_raw, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()

class WhatsAppConnector(BaseConnector):
    source_id = "whatsapp_android"
    category = "chat"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        txt_msgs = self._ingest_txt_chats(src_path)
        db_msgs = self._ingest_msgstore(src_path)
        media_cnt = self._ingest_whatsapp_media(src_path)
        return {"txt_messages": txt_msgs, "db_messages": db_msgs, "media_blobs": media_cnt}

    def _ingest_txt_chats(self, root: str) -> int:
        cnt = 0
        items = []
        for r, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith(".txt") and "chat" in f.lower():
                    fp = os.path.join(r, f)
                    with open(fp, "r", encoding="utf-8", errors="ignore") as tf:
                        for line in tf:
                            parsed = parse_whatsapp_txt_line(line.strip())
                            if parsed:
                                raw_ts, sender, msg = parsed
                                ts_utc = parse_txt_timestamp(raw_ts)
                                iid = str(uuid.uuid4())
                                items.append({
                                    "id": iid,
                                    "source_id": self.source_id,
                                    "source_native_id": f"{f}:{cnt}",
                                    "item_type": "chat_msg",
                                    "timestamp_utc": ts_utc,
                                    "summary_text": msg[:100],
                                    "attributes_json": {"sender": sender, "raw_message": msg}
                                })
                                cnt += 1
                                if len(items) >= 2000:
                                    self.db.batch_insert_timeline_items(items)
                                    items = []
        if items:
            self.db.batch_insert_timeline_items(items)
        return cnt

    def _ingest_msgstore(self, root: str) -> int:
        db_path = None
        for r, _, fs in os.walk(root):
            for f in fs:
                if f == "msgstore.db":
                    db_path = os.path.join(r, f)
                    break
            if db_path:
                break
        if not db_path:
            return 0

        cnt = 0
        items = []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            if not cur.fetchone():
                conn.close()
                return 0
            cur.execute("SELECT key_id, timestamp, text_data, from_me FROM messages WHERE text_data IS NOT NULL LIMIT 50000")
            rows = cur.fetchall()
            for row in rows:
                ts = row["timestamp"]
                ts_utc = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).isoformat() if ts else datetime.now(timezone.utc).isoformat()
                items.append({
                    "source_id": self.source_id,
                    "source_native_id": row["key_id"] or str(uuid.uuid4()),
                    "item_type": "chat_msg",
                    "timestamp_utc": ts_utc,
                    "summary_text": (row["text_data"] or "")[:100],
                    "attributes_json": {"from_me": row["from_me"], "text": row["text_data"]}
                })
                cnt += 1
                if len(items) >= 2000:
                    self.db.batch_insert_timeline_items(items)
                    items = []
            conn.close()
        except Exception:
            pass

        if items:
            self.db.batch_insert_timeline_items(items)
        return cnt

    def _ingest_whatsapp_media(self, root: str) -> int:
        cnt = 0
        for r, _, fs in os.walk(root):
            if "media" not in r.lower() and "whatsapp" not in r.lower():
                continue
            for f in fs:
                ext = os.path.splitext(f)[1].lower()
                if ext not in {".jpg", ".jpeg", ".mp4", ".opus", ".m4a", ".webp"}:
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
                can_rel = os.path.relpath(mp, root)

                ph, dh = None, None
                if ext in {".jpg", ".jpeg"}:
                    ph, dh = compute_perceptual_hashes(mp)

                self.db.upsert_blob(h, sz, mime, ext, can_rel, ph, dh)
                cnt += 1
        return cnt
