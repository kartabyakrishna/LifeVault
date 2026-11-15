import hashlib
import os

def compute_sha256(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file efficiently using streaming chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def verify_file_integrity(source_path: str, target_path: str) -> bool:
    """Verify that source and target files match in size and SHA-256 hash."""
    if not os.path.exists(source_path) or not os.path.exists(target_path):
        return False
    if os.path.getsize(source_path) != os.path.getsize(target_path):
        return False
    return compute_sha256(source_path) == compute_sha256(target_path)
