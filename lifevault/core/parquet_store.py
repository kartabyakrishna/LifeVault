import os
import uuid
from typing import Optional, Dict, Any, List
import polars as pl
from .hasher import compute_sha256

class ParquetStore:
    def __init__(self, root_dir: str):
        self.root = root_dir
        os.makedirs(self.root, exist_ok=True)

    def write_partition(self, metric: str, year: int, df: pl.DataFrame) -> Dict[str, Any]:
        ydir = os.path.join(self.root, metric, f"year={year}")
        os.makedirs(ydir, exist_ok=True)
        fname = f"{uuid.uuid4().hex[:8]}.parquet"
        fpath = os.path.join(ydir, fname)
        df.write_parquet(fpath, compression="zstd")
        sz = os.path.getsize(fpath)
        h = compute_sha256(fpath)
        rel = os.path.relpath(fpath, self.root)
        s_utc = str(df["timestamp"].min()) if "timestamp" in df.columns and len(df) > 0 else ""
        e_utc = str(df["timestamp"].max()) if "timestamp" in df.columns and len(df) > 0 else ""
        return {
            "parquet_rel_path": rel,
            "row_count": len(df),
            "sha256": h,
            "byte_size": sz,
            "start_utc": s_utc,
            "end_utc": e_utc
        }

    def read_metric(self, metric: str, year: Optional[int] = None) -> pl.DataFrame:
        mdir = os.path.join(self.root, metric)
        if not os.path.exists(mdir):
            return pl.DataFrame()
        if year is not None:
            ydir = os.path.join(mdir, f"year={year}")
            if not os.path.exists(ydir):
                return pl.DataFrame()
            return pl.read_parquet(os.path.join(ydir, "*.parquet"))
        return pl.read_parquet(os.path.join(mdir, "**", "*.parquet"))

    def query_range(self, metric: str, s_utc: str, e_utc: str) -> pl.DataFrame:
        df = self.read_metric(metric)
        if len(df) == 0 or "timestamp" not in df.columns:
            return df
        return df.filter((pl.col("timestamp") >= s_utc) & (pl.col("timestamp") <= e_utc))
