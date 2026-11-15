from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..core.db import ManifestDatabase
from ..core.parquet_store import ParquetStore

class BaseConnector(ABC):
    source_id: str
    category: str
    parser_version: str

    def __init__(self, db: ManifestDatabase, store: Optional[ParquetStore] = None):
        self.db = db
        self.store = store

    @abstractmethod
    def ingest(self, src_path: str) -> Dict[str, Any]:
        pass
