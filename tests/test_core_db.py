import json
import pytest
from lifevault.core.db import ManifestDatabase

def test_init_and_sources(tmp_path):
    p = str(tmp_path / "test_manifest.db")
    db = ManifestDatabase(p)
    db.register_source("sony_a6700", "camera", "2.0.0", "2026-11-16T00:00:00Z")
    with db.get_connection() as c:
        row = c.execute("SELECT * FROM sources WHERE id = ?", ("sony_a6700",)).fetchone()
        assert row["category"] == "camera"

def test_blob_and_location(tmp_path):
    p = str(tmp_path / "test_manifest.db")
    db = ManifestDatabase(p)
    db.upsert_blob("a" * 64, 1024, "image/jpeg", ".jpg", "2026/2026-11/test.jpg", ph="ffff", dh="0000")
    db.record_blob_location("a" * 64, "T1_NVME", "2026/2026-11/test.jpg", 0, "2026-11-16T00:00:00Z")
    with db.get_connection() as c:
        b = c.execute("SELECT * FROM blobs WHERE sha256 = ?", ("a" * 64,)).fetchone()
        assert b["phash"] == "ffff"
        loc = c.execute("SELECT * FROM blob_locations WHERE blob_sha256 = ?", ("a" * 64,)).fetchone()
        assert loc["tier_id"] == "T1_NVME"

def test_timeline_items_and_links(tmp_path):
    p = str(tmp_path / "test_manifest.db")
    db = ManifestDatabase(p)
    db.register_source("shealth", "health", "2.0.0", "2026-11-16T00:00:00Z")
    it1 = {
        "id": "item-1",
        "source_id": "shealth",
        "item_type": "workout",
        "timestamp_utc": "2026-11-16T06:00:00Z",
        "attributes_json": {"avg_hr": 145}
    }
    it2 = {
        "id": "item-2",
        "source_id": "shealth",
        "item_type": "photo",
        "timestamp_utc": "2026-11-16T06:15:00Z",
        "attributes_json": {}
    }
    db.batch_insert_timeline_items([it1, it2])
    db.link_items("item-1", "item-2", "biometric_context", 0.95, "auto_verified")
    with db.get_connection() as c:
        cnt = c.execute("SELECT count(*) as c FROM timeline_items").fetchone()["c"]
        assert cnt == 2
        lnk = c.execute("SELECT * FROM item_links WHERE item_a_id = ?", ("item-1",)).fetchone()
        assert lnk["confidence"] == 0.95
