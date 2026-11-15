import polars as pl
import pytest
from lifevault.core.db import ManifestDatabase
from lifevault.core.parquet_store import ParquetStore
from lifevault.intelligence.geo_interpolator import GeoInterpolator

def test_geo_interpolator_linear(tmp_path):
    db_p = str(tmp_path / "manifest.db")
    db = ManifestDatabase(db_p)
    store = ParquetStore(str(tmp_path / "telemetry"))

    db.register_source("camera", "camera", "2.0.0", "2026-11-16T00:00:00Z")
    db.insert_timeline_item({
        "id": "photo-noon",
        "source_id": "camera",
        "source_native_id": "noon.jpg",
        "item_type": "photo",
        "timestamp_utc": "2026-11-16T12:05:00+00:00",
        "lat": None,
        "lon": None
    })

    gps_df = pl.DataFrame({
        "timestamp": ["2026-11-16T12:00:00+00:00", "2026-11-16T12:10:00+00:00"],
        "latitude": [25.0, 26.0],
        "longitude": [85.0, 86.0]
    })
    store.write_partition("gps_track", 2026, gps_df)

    interp = GeoInterpolator(db, store)
    updated = interp.interpolate_photos(max_gap_sec=900.0)
    assert updated == 1

    with db.get_connection() as c:
        row = c.execute("SELECT * FROM timeline_items WHERE id = 'photo-noon'").fetchone()
        assert pytest.approx(row["lat"], 0.01) == 25.5
        assert pytest.approx(row["lon"], 0.01) == 85.5
        assert row["geo_source"] == "interpolated_watch_gps"
