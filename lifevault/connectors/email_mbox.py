import email
from email.utils import parsedate_to_datetime
import mailbox
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .base import BaseConnector
from ..core.hasher import compute_sha256

class EmailConnector(BaseConnector):
    source_id = "personal_email"
    category = "email"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        cnt = 0
        items = []

        for r, _, fs in os.walk(src_path):
            for f in fs:
                fp = os.path.join(r, f)
                ext = os.path.splitext(f)[1].lower()
                if ext == ".mbox":
                    cnt += self._parse_mbox(fp, items)
                elif ext == ".eml":
                    cnt += self._parse_eml(fp, items)

        if items:
            self.db.batch_insert_timeline_items(items)
        return {"emails_indexed": cnt}

    def _parse_mbox(self, fp: str, items: list) -> int:
        cnt = 0
        try:
            mb = mailbox.mbox(fp)
            for msg in mb:
                it = self._convert_msg(msg, fp)
                if it:
                    items.append(it)
                    cnt += 1
        except Exception:
            pass
        return cnt

    def _parse_eml(self, fp: str, items: list) -> int:
        try:
            with open(fp, "rb") as f:
                msg = email.message_from_binary_file(f)
            it = self._convert_msg(msg, fp)
            if it:
                items.append(it)
                return 1
        except Exception:
            pass
        return 0

    def _convert_msg(self, msg: Any, src_file: str) -> Optional[Dict[str, Any]]:
        mid = msg.get("Message-ID") or str(uuid.uuid4())
        subj = msg.get("Subject", "")
        sender = msg.get("From", "")
        dt_raw = msg.get("Date")

        ts_utc = datetime.now(timezone.utc).isoformat()
        if dt_raw:
            try:
                dt = parsedate_to_datetime(dt_raw)
                ts_utc = dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass

        return {
            "source_id": self.source_id,
            "source_native_id": mid,
            "item_type": "email",
            "timestamp_utc": ts_utc,
            "summary_text": subj[:150],
            "attributes_json": {"from": sender, "subject": subj, "file": os.path.basename(src_file)}
        }
