import polars as pl
import pytest
from lifevault.core.parquet_store import ParquetStore

def test_parquet_store_write_and_query(tmp_path):
    store = ParquetStore(str(tmp_path))
    df = pl.DataFrame({
        "timestamp": ["2026-11-16T06:00:00Z", "2026-11-16T06:01:00Z", "2026-11-16T06:02:00Z"],
        "heart_rate": [120, 125, 128]
    })
    meta = store.write_partition("heart_rate", 2026, df)
    assert meta["row_count"] == 3
    assert meta["sha256"] is not None

    read_df = store.read_metric("heart_rate", 2026)
    assert len(read_df) == 3
    assert read_df["heart_rate"].to_list() == [120, 125, 128]

    filtered = store.query_range("heart_rate", "2026-11-16T06:00:00Z", "2026-11-16T06:01:00Z")
    assert len(filtered) == 2
