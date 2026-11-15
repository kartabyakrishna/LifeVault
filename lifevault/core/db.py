import json
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_V2 = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_bundles (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    rel_path TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,
    byte_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    ext TEXT NOT NULL,
    phash TEXT,
    dhash TEXT,
    duration_ms INTEGER,
    canonical_rel_path TEXT NOT NULL,
    scrub_verified_at TEXT
);

CREATE TABLE IF NOT EXISTS blob_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blob_sha256 TEXT NOT NULL REFERENCES blobs(sha256),
    tier_id TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    is_quarantined INTEGER DEFAULT 0,
    verified_at TEXT NOT NULL,
    UNIQUE(blob_sha256, tier_id, rel_path)
);

CREATE TABLE IF NOT EXISTS timeline_items (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    bundle_id TEXT REFERENCES raw_bundles(id),
    source_native_id TEXT,
    item_type TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    end_timestamp_utc TEXT,
    tz_offset TEXT,
    lat REAL,
    lon REAL,
    geo_source TEXT,
    primary_blob_sha256 TEXT REFERENCES blobs(sha256),
    summary_text TEXT,
    attributes_json TEXT NOT NULL,
    UNIQUE(source_id, source_native_id)
);

CREATE TABLE IF NOT EXISTS telemetry_partitions (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    metric_type TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    parquet_rel_path TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_a_id TEXT NOT NULL REFERENCES timeline_items(id),
    item_b_id TEXT NOT NULL REFERENCES timeline_items(id),
    link_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    review_status TEXT DEFAULT 'pending',
    evidence_json TEXT,
    UNIQUE(item_a_id, item_b_id, link_type)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases_json TEXT
);

CREATE TABLE IF NOT EXISTS item_entities (
    item_id TEXT NOT NULL REFERENCES timeline_items(id),
    entity_id TEXT NOT NULL REFERENCES entities(id),
    role TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (item_id, entity_id, role)
);

CREATE TABLE IF NOT EXISTS albums (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS album_items (
    album_id TEXT NOT NULL REFERENCES albums(id),
    item_id TEXT NOT NULL REFERENCES timeline_items(id),
    added_at TEXT NOT NULL,
    PRIMARY KEY (album_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_items_time ON timeline_items(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_items_type ON timeline_items(item_type);
CREATE INDEX IF NOT EXISTS idx_blobs_phash ON blobs(phash);
"""

class ManifestDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        p = os.path.dirname(os.path.abspath(db_path))
        if p:
            os.makedirs(p, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.get_connection() as c:
            c.executescript(SCHEMA_V2)

    def register_source(self, s_id: str, cat: str, ver: str, created: str):
        with self.get_connection() as c:
            c.execute(
                "INSERT OR IGNORE INTO sources (id, category, parser_version, created_at) VALUES (?, ?, ?, ?)",
                (s_id, cat, ver, created)
            )

    def insert_raw_bundle(self, b_id: str, s_id: str, rel: str, h: str, sz: int, ing: str):
        with self.get_connection() as c:
            c.execute(
                "INSERT INTO raw_bundles (id, source_id, rel_path, sha256, byte_size, ingested_at) VALUES (?, ?, ?, ?, ?, ?)",
                (b_id, s_id, rel, h, sz, ing)
            )

    def upsert_blob(self, h: str, sz: int, mime: str, ext: str, can_rel: str, ph: Optional[str] = None, dh: Optional[str] = None, dur: Optional[int] = None):
        with self.get_connection() as c:
            c.execute(
                """
                INSERT INTO blobs (sha256, byte_size, mime_type, ext, phash, dhash, duration_ms, canonical_rel_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    phash = coalesce(excluded.phash, blobs.phash),
                    dhash = coalesce(excluded.dhash, blobs.dhash),
                    duration_ms = coalesce(excluded.duration_ms, blobs.duration_ms)
                """,
                (h, sz, mime, ext, ph, dh, dur, can_rel)
            )

    def record_blob_location(self, h: str, tier: str, rel: str, quar: int, ver: str):
        with self.get_connection() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO blob_locations (blob_sha256, tier_id, rel_path, is_quarantined, verified_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (h, tier, rel, quar, ver)
            )

    def insert_timeline_item(self, item: Dict[str, Any]) -> str:
        iid = item.get("id") or str(uuid.uuid4())
        attr = item.get("attributes_json", "{}")
        if isinstance(attr, dict):
            attr = json.dumps(attr)
        with self.get_connection() as c:
            c.execute(
                """
                INSERT INTO timeline_items (
                    id, source_id, bundle_id, source_native_id, item_type,
                    timestamp_utc, end_timestamp_utc, tz_offset, lat, lon,
                    geo_source, primary_blob_sha256, summary_text, attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    iid, item["source_id"], item.get("bundle_id"), item.get("source_native_id"),
                    item["item_type"], item["timestamp_utc"], item.get("end_timestamp_utc"),
                    item.get("tz_offset"), item.get("lat"), item.get("lon"),
                    item.get("geo_source"), item.get("primary_blob_sha256"),
                    item.get("summary_text"), attr
                )
            )
        return iid

    def batch_insert_timeline_items(self, items: List[Dict[str, Any]]):
        rows = []
        for it in items:
            iid = it.get("id") or str(uuid.uuid4())
            attr = it.get("attributes_json", "{}")
            if isinstance(attr, dict):
                attr = json.dumps(attr)
            rows.append((
                iid, it["source_id"], it.get("bundle_id"), it.get("source_native_id"),
                it["item_type"], it["timestamp_utc"], it.get("end_timestamp_utc"),
                it.get("tz_offset"), it.get("lat"), it.get("lon"),
                it.get("geo_source"), it.get("primary_blob_sha256"),
                it.get("summary_text"), attr
            ))
        with self.get_connection() as c:
            c.executemany(
                """
                INSERT OR IGNORE INTO timeline_items (
                    id, source_id, bundle_id, source_native_id, item_type,
                    timestamp_utc, end_timestamp_utc, tz_offset, lat, lon,
                    geo_source, primary_blob_sha256, summary_text, attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )

    def register_telemetry_partition(self, pid: str, sid: str, mtype: str, s_utc: str, e_utc: str, rel: str, rows: int, h: str):
        with self.get_connection() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO telemetry_partitions (
                    id, source_id, metric_type, start_utc, end_utc, parquet_rel_path, row_count, sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, sid, mtype, s_utc, e_utc, rel, rows, h)
            )

    def link_items(self, a_id: str, b_id: str, ltype: str, conf: float, status: str = "pending", ev: Optional[Dict] = None):
        ev_s = json.dumps(ev) if ev else None
        with self.get_connection() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO item_links (item_a_id, item_b_id, link_type, confidence, review_status, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (a_id, b_id, ltype, conf, status, ev_s)
            )
