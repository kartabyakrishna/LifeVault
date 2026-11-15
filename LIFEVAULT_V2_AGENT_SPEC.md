# LifeVault v2.0: Sovereign Personal Data Lakehouse & Archivist Specification

## 1. System Objective & Architectural Pivot
LifeVault is pivoting from a media-only directory organizer into a **Sovereign Personal Data Lakehouse & Cryptographic Archivist**. It ingests, verifies, cross-links, and preserves ALL human-generated digital artifacts across a multi-decade lifespan:
1. **Discrete Media & Documents:** Camera RAWs/JPEGs (Sony a6700, mobile DCIM), scanned heritage albums, 10,000+ CubeCall/WhatsApp voice recordings, PDFs, financial statements.
2. **Semi-Structured Communication Graphs:** WhatsApp (`msgstore.db.crypt15` & TXT exports), Google Takeout, Snapchat Memories, personal Gmail (`.mbox`) and personal Outlook (`.eml`/PST). *Strict Exclusion: Zero corporate/work data ingestion.*
3. **High-Frequency Wearable & Biometric Telemetry:** Samsung Health data dumps (Galaxy Watch Ultra 2 heart rate, HRV, sleep stages, respiratory rate, GPX/live_data cycling & strength workouts), Google Maps Timeline location history.

### Non-Negotiable Architectural Invariants
* **Zero Deletion & Zero Byte-Mutation:** Master media blobs are strictly read-only after ingestion. Never run `exiftool` in-place on master files (which alters SHA-256 hashes and breaks cross-drive audits). Store metadata overrides in SQLite `attributes_json` or adjacent `.xmp` sidecar files.
* **No Filesystem Hardlinks for Albums:** Deprecate NTFS hardlink virtual albums. All albums, tags, and person clusters must be relational mappings in SQLite to maintain cross-platform compatibility and prevent shared-inode corruption.
* **Hybrid Storage Engine:** 
  * **SQLite (WAL Mode):** Stores provenance bundles, physical blob ledgers, discrete timeline items, person entities, and probabilistic cross-source links.
  * **Apache Parquet (via Polars/PyArrow):** Stores high-frequency time-series sensor streams (1Hz/minute heart rate, GPS trackpoints, accelerometer data) under `_Telemetry/<metric_type>/year=<YYYY>/part.parquet`.
* **Probabilistic Linking over Blind Deduplication:** Exact SHA-256 matches go to `_Duplicates_Quarantine/`. Cross-source recompressed derivatives (e.g., original camera photo vs. WhatsApp image) are linked via Perceptual Hashing (`pHash`/`dHash`) + temporal proximity inside the `item_links` table with an explicit confidence score (`0.0` to `1.0`) and `review_status`.

---

## 2. Open-Source Reference Repos to Pull Patterns From
When implementing connectors and engines, inspect, adapt, or wrap the following open-source libraries rather than writing parsers from scratch:

1. **Samsung Health & Wearable Telemetry:**
   * `https://github.com/Devasy/samsung-health-sdk` — Reference for auto-detecting Samsung Health CSV metadata rows (skipping line 1 metadata header), parsing `jsons/` subdirectories for minute-level binning, and computing HRV/sleep/cardiac efficiency metrics.
   * `https://github.com/GlucoseDAO/samsung_health_extractor` — Reference for using `Polars` and `Typer` to merge general `tracker.heart_rate` streams with high-frequency (1Hz) workout `live_data.json` streams and handling trailing commas in Samsung CSVs.
   * `https://github.com/breakpointforensics/Samsung-Secure-Health-Data-Parser-` — Reference for decompressing GZIP-compressed JSON blobs inside Samsung Health live exercise tracking sessions.
2. **WhatsApp Decryption & Chat Parsing:**
   * `https://github.com/ElDavoo/wa-crypt-tools` — Use as a dependency (`pip install wa-crypt-tools`) to decrypt Android `.crypt14`/`.crypt15` E2E backups using the user's 64-character hex key into a raw `msgstore.db` SQLite database. Never write custom AES-GCM decryption.
   * `https://github.com/MasterScrat/Chatistics` — Reference for normalizing multi-platform chat logs into unified DataFrame schemas.
3. **Google Takeout & EXIF Sidecars:**
   * `https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper` & `https://github.com/garbageslam/PhotoMigrator` — Reference for matching Google Takeout's truncated/quirky `.json` sidecar naming conventions (`photo(1).jpg.json`, `.supplemental-metadata.json`) to their parent media files. *Crucial: Adapt the matching logic, but write extracted timestamps/GPS to SQLite and `.xmp` sidecars instead of mutating the original JPEG/MP4.*
4. **Personal Data Lakehouse & Timeline Architectures:**
   * `https://github.com/karlicoss/HPI` (Human Programming Interface) — Reference for modular connector design and normalizing heterogeneous personal data exports.
   * `https://github.com/mholt/timelinize` & `https://github.com/dogsheep` — Reference for entity-linking, relational timeline schemas, and cross-source schema design.

---

## 3. Target Directory Topology

```text
LifeVault/
├── pyproject.toml                 # Dependencies: polars, pyarrow, imagehash, pillow, wa-crypt-tools, rich, typer, pytest
├── lifevault/
│   ├── cli.py                     # Unified Typer CLI (ingest, sync, scrub, audit, rollback, link, telemetry)
│   ├── core/
│   │   ├── db.py                  # SQLite v2.0 schema manager & transactional batch writer
│   │   ├── filesystem.py          # Atomic copy-verify-swap, cross-volume safety
│   │   ├── hasher.py              # Multi-core streaming SHA-256 + imagehash (pHash/dHash)
│   │   └── parquet_store.py       # Polars/PyArrow partitioned writer & DuckDB/Polars query interface
│   ├── connectors/
│   │   ├── base.py                # Abstract BaseConnector contract
│   │   ├── dcim.py                # Camera RAW (Sony ARW) & mobile DCIM ingestor
│   │   ├── samsung_health.py      # CSV + GZIP/JSON live_data + location_data stitcher -> SQLite + Parquet
│   │   ├── whatsapp.py            # wa-crypt-tools wrapper + msgstore.db & TXT chat/media linker
│   │   ├── google_takeout.py      # Sidecar JSON resolver (non-destructive metadata extraction)
│   │   ├── snapchat.py            # Memories JSON parser + overlay merger
│   │   ├── audio_calls.py         # CubeCall filename parser (caller, timestamp) + audio duration extractor
│   │   └── email_mbox.py          # Personal Gmail .mbox & Outlook .eml parser + attachment hash linker
│   ├── intelligence/
│   │   ├── near_dup.py            # Hamming-distance pHash matcher & temporal window linker
│   │   ├── geo_interpolator.py    # Intersects photo timestamps with Watch/Maps GPS Parquet streams
│   │   └── asr_benchmark.py       # WER evaluation harness for Whisper vs IndicConformer on call audio
│   └── recovery/
│       ├── auditor.py             # Cross-drive forensic comparator & scheduled bit-rot scrubber
│       ├── parity.py              # PAR2 wrapper for cold-vault bit-rot self-healing
│       └── rollback.py            # Transactional state restorer
└── tests/
    ├── test_atomic_swap_fault.py  # Simulated mid-copy IOError/disconnect fault-injection tests
    ├── test_shealth_parser.py     # Tests CSV metadata row skipping & live_data JSON merging
    └── test_takeout_sidecar.py    # Tests non-destructive sidecar matching
```

---

## 4. SQLite Database Schema (`v2.0` - `lifevault/core/db.py`)

Implement the following exact schema:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,              -- e.g., 'sony_a6700', 'shealth_watch_ultra2', 'whatsapp_android', 'cubecall'
    category TEXT NOT NULL,           -- 'camera', 'chat', 'health', 'cloud_takeout', 'voice_recorder', 'email'
    parser_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_bundles (
    id TEXT PRIMARY KEY,              -- UUIDv4
    source_id TEXT NOT NULL REFERENCES sources(id),
    rel_path TEXT NOT NULL,           -- Path inside _Raw_Exports/
    sha256 TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,
    byte_size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    ext TEXT NOT NULL,
    phash TEXT,                       -- 64-bit hex perceptual hash
    dhash TEXT,                       -- 64-bit hex difference hash
    duration_ms INTEGER,
    canonical_rel_path TEXT NOT NULL,
    scrub_verified_at TEXT
);

CREATE TABLE IF NOT EXISTS blob_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blob_sha256 TEXT NOT NULL REFERENCES blobs(sha256),
    tier_id TEXT NOT NULL,            -- 'T1_NVME', 'T2_PATNA_4TB', 'T3_PATNA_1TB', 'T4_TRAVEL', 'B2_OFFSITE'
    rel_path TEXT NOT NULL,
    is_quarantined INTEGER DEFAULT 0,
    verified_at TEXT NOT NULL,
    UNIQUE(blob_sha256, tier_id, rel_path)
);

CREATE TABLE IF NOT EXISTS timeline_items (
    id TEXT PRIMARY KEY,              -- UUIDv4
    source_id TEXT NOT NULL REFERENCES sources(id),
    bundle_id TEXT REFERENCES raw_bundles(id),
    source_native_id TEXT,            -- e.g., Samsung Health datauuid, WhatsApp message key_id, Message-ID
    item_type TEXT NOT NULL,          -- 'photo', 'video', 'call_audio', 'chat_msg', 'workout', 'sleep', 'daily_vitals', 'email', 'doc'
    timestamp_utc TEXT NOT NULL,      -- ISO-8601 UTC
    end_timestamp_utc TEXT,
    tz_offset TEXT,                   -- e.g., '+05:30'
    lat REAL,
    lon REAL,
    geo_source TEXT,                  -- 'exif', 'takeout_json', 'interpolated_watch_gps'
    primary_blob_sha256 TEXT REFERENCES blobs(sha256),
    summary_text TEXT,
    attributes_json TEXT NOT NULL,    -- JSON: EXIF, workout avg_hr, max_hr, distance_m, sleep_score, sidecar tags
    UNIQUE(source_id, source_native_id)
);

CREATE TABLE IF NOT EXISTS telemetry_partitions (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    metric_type TEXT NOT NULL,        -- 'heart_rate', 'gps_track', 'steps_minute', 'sleep_stage', 'hrv', 'respiratory_rate'
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
    link_type TEXT NOT NULL,          -- 'exact_sha256', 'near_dup_phash', 'reply_to', 'attachment_of', 'biometric_context'
    confidence REAL NOT NULL,
    review_status TEXT DEFAULT 'pending', -- 'auto_verified', 'pending', 'human_confirmed', 'human_rejected'
    evidence_json TEXT,
    UNIQUE(item_a_id, item_b_id, link_type)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,        -- 'person', 'place', 'device'
    canonical_name TEXT NOT NULL,
    aliases_json TEXT                 -- Phone numbers, JIDs, email addresses
);

CREATE TABLE IF NOT EXISTS item_entities (
    item_id TEXT NOT NULL REFERENCES timeline_items(id),
    entity_id TEXT NOT NULL REFERENCES entities(id),
    role TEXT NOT NULL,               -- 'sender', 'recipient', 'caller', 'participant', 'subject'
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
```

---

## 5. Detailed Connector Specifications

### A. `SamsungHealthConnector` (`lifevault/connectors/samsung_health.py`)
1. **Quirk Handling:** Samsung Health CSVs (`com.samsung.shealth.*.csv`) contain a metadata line on Row 1, column headers on Row 2, and a trailing comma on every data row. Auto-detect and skip Row 1 using Polars/Pandas.
2. **Exercise & Live Telemetry Stitching:**
   * Read `com.samsung.shealth.exercise.csv`. Each row represents a workout (`item_type = 'workout'`, `source_native_id = datauuid`).
   * Locate the matching `jsons/com.samsung.shealth.exercise/<char>/<datauuid>.live_data.json` (and `.location_data.json` if outdoor cycling/running). Note: Some blobs may be GZIP-compressed; check magic bytes `\x1f\x8b` and decompress if needed.
   * Extract summary metrics (`distance`, `duration`, `mean_heart_rate`, `max_heart_rate`, `calories`, `exercise_type`) into `timeline_items.attributes_json`.
   * Write the high-frequency (1Hz) heart rate, cadence, speed, and lat/lon points from `live_data.json` and `location_data.json` into `_Telemetry/workout_streams/year=<YYYY>/` as Parquet, and register the partition in `telemetry_partitions`.
3. **Continuous Vitals (`tracker.heart_rate`, `sleep`, `stress`, `hrv`):**
   * Create one `timeline_items` entry per sleep session (`com.samsung.shealth.sleep.csv`).
   * Funnel minute-level heart rate, HRV, respiratory rate, and sleep stages into partitioned Parquet files via `parquet_store.py`.

### B. `GeoInterpolator` (`lifevault/intelligence/geo_interpolator.py`)
* Query `timeline_items` where `item_type IN ('photo', 'video')` and `lat IS NULL`.
* Query `telemetry_partitions` (`metric_type = 'gps_track'`) for GPS points within `±15 minutes` of `timestamp_utc`.
* Perform linear timestamp interpolation between the two closest GPS points. If the bounding time gap is under 10 minutes and spatial distance is under 500 meters, update `timeline_items.lat`, `timeline_items.lon`, and set `geo_source = 'interpolated_watch_gps'`.

### C. `GoogleTakeoutConnector` (`lifevault/connectors/google_takeout.py`)
* Match media files to their `.json` sidecars (handling truncated filenames and numbered duplicates like `IMG_001(1).jpg` -> `IMG_001.jpg(1).json`).
* Hash and ingest the untouched media file into `blobs`.
* Parse `photoTakenTime.timestamp`, `geoData.latitude`, `geoData.longitude`, and `people` from the JSON sidecar and store them in `timeline_items` without modifying the image file on disk.

### D. `WhatsAppConnector` (`lifevault/connectors/whatsapp.py`)
* Support both `.txt` chat exports and decrypted `msgstore.db` SQLite databases (decrypted via `wa-crypt-tools` CLI/library).
* Ingest every message into `timeline_items` (`item_type = 'chat_msg'`).
* When a message references a media attachment (`Media/WhatsApp Images/...` or `WhatsApp Voice Notes/...`), hash the media file into `blobs`, link `primary_blob_sha256`, and run `near_dup.py` to link recompressed photos against high-res camera originals in `blobs` via `phash`.

---

## 6. Execution Phases for the Coding Agent

* **Step 1 (Core & Fault-Tolerant Tests):** Implement `lifevault/core/db.py` (`v2.0` schema), `parquet_store.py`, and `hasher.py` (adding `imagehash` pHash/dHash calculation alongside SHA-256). Write `pytest` unit tests including simulated mid-copy I/O fault injection for `filesystem.py` and rollback verification.
* **Step 2 (Connector Base & Samsung Health):** Implement `connectors/base.py` and `connectors/samsung_health.py`. Test on a sample Samsung Health export folder to verify CSV header handling, `live_data.json` merging, and Parquet output.
* **Step 3 (Takeout, Snapchat & Audio Calls):** Implement `google_takeout.py`, `snapchat.py`, and `audio_calls.py` (parsing CubeCall filenames into caller entity + timestamp).
* **Step 4 (WhatsApp & Cross-Source Linker):** Implement `whatsapp.py` and `intelligence/near_dup.py` + `geo_interpolator.py`.
