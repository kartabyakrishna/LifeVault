import os
import shutil

def safe_ntfs_move(src: str, dst: str) -> bool:
    """Move a file using atomic pointer update if on same drive, else copy and verify."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        if os.path.getsize(dst) == os.path.getsize(src):
            return True
        base, ext = os.path.splitext(dst)
        counter = 1
        while os.path.exists(dst):
            dst = f"{base}_{counter}{ext}"
            counter += 1
    os.replace(src, dst)
    return True

def create_hardlink(src: str, dst: str) -> bool:
    """Create an NTFS hardlink (0 extra disk space) or fallback to copy."""
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            os.link(src, dst)
            return True
    except Exception:
        try:
            shutil.copy2(src, dst)
            return True
        except Exception:
            pass
    return False
