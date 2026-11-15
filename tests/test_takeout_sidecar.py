import json
import pytest
from lifevault.core.db import ManifestDatabase
from lifevault.connectors.google_takeout import GoogleTakeoutConnector, find_sidecar_json

def test_find_sidecar_json(tmp_path):
    media = tmp_path / "IMG_2026(1).jpg"
    media.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
    sc = tmp_path / "IMG_2026.jpg(1).json"
    sc.write_text('{"photoTakenTime": {"timestamp": "1731720000"}}')
    found = find_sidecar_json(str(media))
    assert found == str(sc)

def test_google_takeout_ingest_preserves_bytes(tmp_path):
    db_p = str(tmp_path / "manifest.db")
    db = ManifestDatabase(db_p)

    media = tmp_path / "sunset.jpg"
    raw_bytes = b"\xff\xd8\xff\xe0" + b"\x12\x34\x56\x78"
    media.write_bytes(raw_bytes)

    sc = tmp_path / "sunset.jpg.json"
    sc.write_text(json.dumps({
        "photoTakenTime": {"timestamp": "1731720000"},
        "geoData": {"latitude": 25.5941, "longitude": 85.1376}
    }))

    conn = GoogleTakeoutConnector(db)
    res = conn.ingest(str(tmp_path))
    assert res["media_items"] == 1
    assert media.read_bytes() == raw_bytes

    with db.get_connection() as c:
        it = c.execute("SELECT * FROM timeline_items WHERE source_id = 'google_takeout'").fetchone()
        assert it is not None
        assert it["lat"] == 25.5941
        assert it["lon"] == 85.1376
        assert it["geo_source"] == "takeout_json"
