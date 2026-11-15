import hashlib
import os
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import imagehash

def compute_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def compute_perceptual_hashes(path: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        with Image.open(path) as img:
            ph = str(imagehash.phash(img))
            dh = str(imagehash.dhash(img))
            return ph, dh
    except Exception:
        return None, None

def hamming_distance(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")

def verify_file_integrity(src: str, dst: str) -> bool:
    if not os.path.exists(src) or not os.path.exists(dst):
        return False
    if os.path.getsize(src) != os.path.getsize(dst):
        return False
    return compute_sha256(src) == compute_sha256(dst)

def batch_compute_sha256(paths: List[str], max_w: Optional[int] = None) -> Dict[str, str]:
    if not paths:
        return {}
    w = max_w or min(32, (os.cpu_count() or 4) * 2)
    res = {}
    def _hash(p: str):
        try:
            return p, compute_sha256(p)
        except (OSError, IOError):
            return p, None
    with ThreadPoolExecutor(max_workers=w) as ex:
        futs = {ex.submit(_hash, p): p for p in paths}
        for f in as_completed(futs):
            p, h = f.result()
            if h is not None:
                res[p] = h
    return res
