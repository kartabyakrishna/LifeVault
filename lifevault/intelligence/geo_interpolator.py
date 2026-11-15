from datetime import datetime, timezone
from typing import Optional, Tuple
import polars as pl
from ..core.db import ManifestDatabase
from ..core.parquet_store import ParquetStore

def parse_iso_utc(ts: str) -> Optional[float]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None

class GeoInterpolator:
    def __init__(self, db: ManifestDatabase, store: ParquetStore):
        self.db = db
        self.store = store

    def interpolate_photos(self, max_gap_sec: float = 600.0) -> int:
        with self.db.get_connection() as c:
            photos = c.execute(
                """
                SELECT id, timestamp_utc 
                FROM timeline_items 
                WHERE item_type IN ('photo', 'video') AND lat IS NULL
                """
            ).fetchall()

        if not photos:
            return 0

        gps_df = self.store.read_metric("gps_track")
        if len(gps_df) == 0:
            gps_df = self.store.read_metric("workout_streams")
        if len(gps_df) == 0 or "latitude" not in gps_df.columns or "longitude" not in gps_df.columns:
            return 0

        ts_col = "timestamp" if "timestamp" in gps_df.columns else gps_df.columns[0]
        gps_rows = gps_df.filter(
            pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null()
        ).select([ts_col, "latitude", "longitude"]).sort(ts_col)

        if len(gps_rows) == 0:
            return 0

        times = [parse_iso_utc(t) for t in gps_rows[ts_col].to_list()]
        lats = gps_rows["latitude"].to_list()
        lons = gps_rows["longitude"].to_list()
        valid = [(t, lat, lon) for t, lat, lon in zip(times, lats, lons) if t is not None]
        if not valid:
            return 0

        updated = 0
        for p in photos:
            pt = parse_iso_utc(p["timestamp_utc"])
            if pt is None:
                continue

            prev_pt, next_pt = None, None
            for v in valid:
                if v[0] <= pt:
                    prev_pt = v
                elif v[0] > pt:
                    next_pt = v
                    break

            if prev_pt and next_pt:
                dt = next_pt[0] - prev_pt[0]
                if 0 < dt <= max_gap_sec:
                    f = (pt - prev_pt[0]) / dt
                    lat = prev_pt[1] + f * (next_pt[1] - prev_pt[1])
                    lon = prev_pt[2] + f * (next_pt[2] - prev_pt[2])
                    with self.db.get_connection() as c:
                        c.execute(
                            "UPDATE timeline_items SET lat = ?, lon = ?, geo_source = ? WHERE id = ?",
                            (lat, lon, "interpolated_watch_gps", p["id"])
                        )
                    updated += 1
            elif prev_pt and abs(pt - prev_pt[0]) <= 300.0:
                with self.db.get_connection() as c:
                    c.execute(
                        "UPDATE timeline_items SET lat = ?, lon = ?, geo_source = ? WHERE id = ?",
                        (prev_pt[1], prev_pt[2], "interpolated_watch_gps", p["id"])
                    )
                updated += 1

        return updated
