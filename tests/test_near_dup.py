import pytest
from PIL import Image
from lifevault.core.db import ManifestDatabase
from lifevault.intelligence.near_dup import NearDuplicateMatcher

def test_near_duplicate_matcher(tmp_path):
    db_p = str(tmp_path / "manifest.db")
    db = ManifestDatabase(db_p)

    db.register_source("camera", "camera", "2.0.0", "2026-11-16T00:00:00Z")
    db.upsert_blob("hash_a" + "0" * 58, 2048, "image/jpeg", ".jpg", "a.jpg", ph="ffff0000ffff0000")
    db.upsert_blob("hash_b" + "0" * 58, 1024, "image/jpeg", ".jpg", "b.jpg", ph="ffff0000ffff0001")

    db.insert_timeline_item({
        "id": "it-1",
        "source_id": "camera",
        "source_native_id": "photo_1",
        "item_type": "photo",
        "timestamp_utc": "2026-11-16T10:00:00Z",
        "primary_blob_sha256": "hash_a" + "0" * 58
    })
    db.insert_timeline_item({
        "id": "it-2",
        "source_id": "camera",
        "source_native_id": "photo_2",
        "item_type": "photo",
        "timestamp_utc": "2026-11-16T10:05:00Z",
        "primary_blob_sha256": "hash_b" + "0" * 58
    })

    matcher = NearDuplicateMatcher(db)
    linked = matcher.link_perceptual_duplicates(max_dist=4)
    assert linked == 1

    with db.get_connection() as c:
        row = c.execute("SELECT * FROM item_links WHERE item_a_id = 'it-1'").fetchone()
        assert row is not None
        assert row["link_type"] == "near_dup_phash"
        assert row["confidence"] >= 0.95
        assert row["review_status"] == "auto_verified"
