import pytest
from lifevault.core.db import ManifestDatabase
from lifevault.connectors.audio_calls import AudioCallsConnector, parse_call_filename

def test_parse_call_filename():
    caller, ts = parse_call_filename("Phone (+919876543210)_20240915123000.m4a")
    assert caller == "+919876543210"
    assert "2024-09-15" in ts

    caller2, ts2 = parse_call_filename("Call with Mummy_20230510.amr")
    assert caller2 == "Mummy"
    assert "2023-05-10" in ts2

def test_audio_calls_ingest(tmp_path):
    db_p = str(tmp_path / "manifest.db")
    db = ManifestDatabase(db_p)

    audio_file = tmp_path / "Call with Papa_20261115180000.m4a"
    audio_file.write_bytes(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 64)

    conn = AudioCallsConnector(db)
    res = conn.ingest(str(tmp_path))
    assert res["calls_indexed"] == 1

    with db.get_connection() as c:
        it = c.execute("SELECT * FROM timeline_items WHERE source_id = 'cubecall'").fetchone()
        assert it is not None
        assert it["item_type"] == "call_audio"

        ent = c.execute("SELECT * FROM entities WHERE canonical_name = 'Papa'").fetchone()
        assert ent is not None
        assert ent["entity_type"] == "person"

        ie = c.execute("SELECT * FROM item_entities WHERE item_id = ?", (it["id"],)).fetchone()
        assert ie is not None
        assert ie["role"] == "caller"
