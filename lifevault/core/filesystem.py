import os
import shutil
import uuid

def safe_atomic_move(src: str, dst: str, force_copy: bool = False) -> bool:
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            if os.path.samefile(src, dst):
                return True
        except (OSError, AttributeError):
            pass
        b, e = os.path.splitext(dst)
        c = 1
        while os.path.exists(dst):
            dst = f"{b}_{c}{e}"
            c += 1

    sd = os.path.splitdrive(os.path.abspath(src))[0].lower()
    dd = os.path.splitdrive(os.path.abspath(dst))[0].lower()

    if sd == dd and not force_copy:
        try:
            os.replace(src, dst)
            return True
        except OSError:
            pass

    tmp = f"{dst}.tmp_{uuid.uuid4().hex[:8]}"
    try:
        shutil.copy2(src, tmp)
        if os.path.getsize(tmp) != os.path.getsize(src):
            if os.path.exists(tmp):
                os.remove(tmp)
            raise IOError("Size mismatch")
        os.replace(tmp, dst)
        os.remove(src)
        return True
    except Exception as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise exc

def create_hardlink(src: str, dst: str) -> bool:
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
