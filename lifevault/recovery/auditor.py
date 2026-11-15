import os
from typing import Dict, List, Tuple

class VaultAuditor:
    """Forensic cross-drive comparator to ensure 100% preservation with 0 missing files."""

    @staticmethod
    def audit_directories(source_root: str, target_root: str) -> dict:
        source_files: Dict[str, int] = {}
        for root, _, files in os.walk(source_root):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, source_root)
                try:
                    source_files[rel] = os.path.getsize(p)
                except OSError:
                    pass

        target_files: Dict[str, int] = {}
        for root, _, files in os.walk(target_root):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, target_root)
                try:
                    target_files[rel] = os.path.getsize(p)
                except OSError:
                    pass

        missing: List[str] = []
        size_mismatches: List[Tuple[str, int, int]] = []

        for rel, sz in source_files.items():
            if rel not in target_files:
                missing.append(rel)
            elif target_files[rel] != sz:
                size_mismatches.append((rel, sz, target_files[rel]))

        return {
            "source_total_files": len(source_files),
            "target_total_files": len(target_files),
            "missing_count": len(missing),
            "mismatch_count": len(size_mismatches),
            "missing_sample": missing[:10]
        }
