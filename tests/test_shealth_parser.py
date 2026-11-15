import gzip
import json
import os
import pytest
from lifevault.core.db import ManifestDatabase
from lifevault.core.parquet_store import ParquetStore
from lifevault.connectors.samsung_health import SamsungHealthConnector, read_shealth_csv

def test_read_shealth_csv_with_header_and_trailing_comma(tmp_path):
    csv_file = tmp_path / "com.samsung.shealth.exercise.test.csv"
    content = (
        "com.samsung.shealth.exercise,version=1.0\n"
        "datauuid,exercise_type,duration,mean_heart_rate,calorie,\n"
        "uuid-1234,1001,3600000,142,350.5,\n"
    )
    csv_file.write_text(content)
    rows = read_shealth_csv(str(csv_file))
    assert len(rows) == 1
    assert rows[0]["datauuid"] == "uuid-1234"
    assert rows[0]["mean_heart_rate"] == "142"

def test_samsung_health_ingest_with_live_data(tmp_path):
    db_p = str(tmp_path / "manifest.db")
    db = ManifestDatabase(db_p)
    p_store = ParquetStore(str(tmp_path / "telemetry"))

    exp_dir = tmp_path / "shealth_export"
    exp_dir.mkdir()
    ex_csv = exp_dir / "com.samsung.shealth.exercise.sample.csv"
    ex_csv.write_text(
        "com.samsung.shealth.exercise,v2\n"
        "datauuid,exercise_type,duration,start_time,mean_heart_rate,\n"
        "workout-999,1001,1800000,1731720000000,150,\n"
    )

    js_dir = exp_dir / "jsons" / "com.samsung.shealth.exercise" / "w"
    js_dir.mkdir(parents=True)
    live_json = js_dir / "workout-999.live_data.json"
    pts = [
        {"start_time": 1731720000000, "heart_rate": 140, "cadence": 80, "speed": 5.2},
        {"start_time": 1731720001000, "heart_rate": 145, "cadence": 82, "speed": 5.4}
    ]
    with gzip.open(str(live_json), "wb") as f:
        f.write(json.dumps(pts).encode("utf-8"))

    conn = SamsungHealthConnector(db, p_store)
    res = conn.ingest(str(exp_dir))
    assert res["workouts"] == 1

    with db.get_connection() as c:
        it = c.execute("SELECT * FROM timeline_items WHERE source_native_id = 'workout-999'").fetchone()
        assert it is not None
        assert it["item_type"] == "workout"
        part = c.execute("SELECT * FROM telemetry_partitions WHERE source_id = 'shealth_watch_ultra2'").fetchone()
        assert part is not None
        assert part["metric_type"] == "workout_streams"
        assert part["row_count"] == 2
