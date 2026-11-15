import os
import pytest
from lifevault.core.filesystem import safe_atomic_move

def test_safe_atomic_move_success(tmp_path):
    s = tmp_path / "src.txt"
    s.write_text("lifevault v2 payload")
    d = tmp_path / "sub" / "dst.txt"
    res = safe_atomic_move(str(s), str(d), force_copy=True)
    assert res is True
    assert not s.exists()
    assert d.read_text() == "lifevault v2 payload"

def test_safe_atomic_move_nonexistent(tmp_path):
    s = tmp_path / "missing.txt"
    d = tmp_path / "dst.txt"
    res = safe_atomic_move(str(s), str(d))
    assert res is False

def test_safe_atomic_move_fault_injection(tmp_path, monkeypatch):
    s = tmp_path / "src.txt"
    s.write_text("unbreakable data")
    d = tmp_path / "dst.txt"

    def fail_copy(src, dst):
        raise IOError("Simulated drive disconnection")

    monkeypatch.setattr("shutil.copy2", fail_copy)
    with pytest.raises(IOError):
        safe_atomic_move(str(s), str(d), force_copy=True)

    assert s.exists()
    assert not d.exists()
    tmps = list(tmp_path.glob("dst.txt.tmp_*"))
    assert len(tmps) == 0
