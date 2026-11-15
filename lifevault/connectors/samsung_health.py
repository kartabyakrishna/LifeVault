import csv
import gzip
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import polars as pl
from .base import BaseConnector

def read_shealth_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if not lines:
        return []
    st = 1 if len(lines) > 1 and lines[0].count(",") < lines[1].count(",") else 0
    clean = []
    for l in lines[st:]:
        sl = l.strip()
        if sl.endswith(","):
            sl = sl[:-1]
        clean.append(sl)
    buf = io.StringIO("\n".join(clean))
    r = csv.DictReader(buf)
    return [row for row in r]

def load_maybe_gzipped_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data.startswith(b"\x1f\x8b"):
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:
        return None

def epoch_ms_to_iso(ms: Any) -> str:
    try:
        v = float(ms)
        if v > 1e11:
            v /= 1000.0
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()

class SamsungHealthConnector(BaseConnector):
    source_id = "shealth_watch_ultra2"
    category = "health"
    parser_version = "2.0.0"

    def ingest(self, src_path: str) -> Dict[str, Any]:
        self.db.register_source(self.source_id, self.category, self.parser_version, datetime.now(timezone.utc).isoformat())
        w_cnt, s_cnt, hr_cnt = 0, 0, 0
        w_cnt = self._process_exercises(src_path)
        s_cnt = self._process_sleep(src_path)
        hr_cnt = self._process_heart_rate(src_path)
        return {"workouts": w_cnt, "sleep_sessions": s_cnt, "heart_rate_records": hr_cnt}

    def _process_exercises(self, root: str) -> int:
        ex_csv = None
        for r, _, fs in os.walk(root):
            for f in fs:
                if f.startswith("com.samsung.shealth.exercise.") and f.endswith(".csv"):
                    ex_csv = os.path.join(r, f)
                    break
            if ex_csv:
                break
        if not ex_csv:
            return 0

        rows = read_shealth_csv(ex_csv)
        items = []
        js_dir = os.path.join(os.path.dirname(ex_csv), "jsons", "com.samsung.shealth.exercise")

        for row in rows:
            uid = row.get("datauuid") or row.get("pkg_name") or str(uuid.uuid4())
            s_time = row.get("start_time") or row.get("create_time") or str(int(datetime.now().timestamp() * 1000))
            e_time = row.get("end_time")
            s_utc = epoch_ms_to_iso(s_time)
            e_utc = epoch_ms_to_iso(e_time) if e_time else None
            y = int(s_utc[:4]) if len(s_utc) >= 4 and s_utc[:4].isdigit() else 2026

            attr = {
                "exercise_type": row.get("exercise_type"),
                "distance": row.get("distance"),
                "duration": row.get("duration"),
                "mean_heart_rate": row.get("mean_heart_rate"),
                "max_heart_rate": row.get("max_heart_rate"),
                "calorie": row.get("calorie")
            }

            pts = []
            if os.path.exists(js_dir):
                c = uid[0] if uid else "0"
                lp = os.path.join(js_dir, c, f"{uid}.live_data.json")
                if not os.path.exists(lp):
                    lp = os.path.join(js_dir, f"{uid}.live_data.json")
                ldata = load_maybe_gzipped_json(lp)
                if isinstance(ldata, list):
                    for p in ldata:
                        t = p.get("start_time") or s_time
                        pts.append({
                            "timestamp": epoch_ms_to_iso(t),
                            "heart_rate": p.get("heart_rate"),
                            "cadence": p.get("cadence"),
                            "speed": p.get("speed")
                        })

            if pts and self.store:
                df = pl.DataFrame(pts)
                pinfo = self.store.write_partition("workout_streams", y, df)
                self.db.register_telemetry_partition(
                    f"part_{uid[:8]}", self.source_id, "workout_streams",
                    pinfo["start_utc"], pinfo["end_utc"], pinfo["parquet_rel_path"],
                    pinfo["row_count"], pinfo["sha256"]
                )

            items.append({
                "source_id": self.source_id,
                "source_native_id": uid,
                "item_type": "workout",
                "timestamp_utc": s_utc,
                "end_timestamp_utc": e_utc,
                "attributes_json": attr
            })

        self.db.batch_insert_timeline_items(items)
        return len(items)

    def _process_sleep(self, root: str) -> int:
        s_csv = None
        for r, _, fs in os.walk(root):
            for f in fs:
                if f.startswith("com.samsung.shealth.sleep.") and f.endswith(".csv"):
                    s_csv = os.path.join(r, f)
                    break
            if s_csv:
                break
        if not s_csv:
            return 0

        rows = read_shealth_csv(s_csv)
        items = []
        for row in rows:
            uid = row.get("datauuid") or str(uuid.uuid4())
            s_time = row.get("start_time") or row.get("create_time") or str(int(datetime.now().timestamp() * 1000))
            e_time = row.get("end_time")
            s_utc = epoch_ms_to_iso(s_time)
            e_utc = epoch_ms_to_iso(e_time) if e_time else None

            attr = {
                "sleep_score": row.get("sleep_score"),
                "duration": row.get("duration"),
                "efficiency": row.get("efficiency")
            }

            items.append({
                "source_id": self.source_id,
                "source_native_id": uid,
                "item_type": "sleep",
                "timestamp_utc": s_utc,
                "end_timestamp_utc": e_utc,
                "attributes_json": attr
            })

        self.db.batch_insert_timeline_items(items)
        return len(items)

    def _process_heart_rate(self, root: str) -> int:
        hr_csv = None
        for r, _, fs in os.walk(root):
            for f in fs:
                if "tracker.heart_rate." in f and f.endswith(".csv"):
                    hr_csv = os.path.join(r, f)
                    break
            if hr_csv:
                break
        if not hr_csv or not self.store:
            return 0

        rows = read_shealth_csv(hr_csv)
        pts = []
        for r in rows:
            st = r.get("start_time") or r.get("create_time")
            hr = r.get("heart_rate")
            if st and hr:
                pts.append({
                    "timestamp": epoch_ms_to_iso(st),
                    "heart_rate": float(hr)
                })

        if pts:
            df = pl.DataFrame(pts)
            y = int(df["timestamp"][0][:4]) if len(df) > 0 and len(df["timestamp"][0]) >= 4 else 2026
            pinfo = self.store.write_partition("heart_rate", y, df)
            self.db.register_telemetry_partition(
                f"part_hr_{uuid.uuid4().hex[:8]}", self.source_id, "heart_rate",
                pinfo["start_utc"], pinfo["end_utc"], pinfo["parquet_rel_path"],
                pinfo["row_count"], pinfo["sha256"]
            )
            return len(pts)
        return 0
