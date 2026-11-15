import pytest
from PIL import Image
from lifevault.core.hasher import (
    compute_sha256,
    compute_perceptual_hashes,
    hamming_distance,
    verify_file_integrity
)

def test_sha256_and_integrity(tmp_path):
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_bytes(b"hello world")
    f2.write_bytes(b"hello world")
    assert verify_file_integrity(str(f1), str(f2)) is True
    f2.write_bytes(b"modified")
    assert verify_file_integrity(str(f1), str(f2)) is False

def test_perceptual_hash_and_hamming(tmp_path):
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    Image.new("RGB", (64, 64), color="red").save(str(img1))
    Image.new("RGB", (64, 64), color="red").save(str(img2))
    ph1, dh1 = compute_perceptual_hashes(str(img1))
    ph2, dh2 = compute_perceptual_hashes(str(img2))
    assert ph1 is not None and ph2 is not None
    assert hamming_distance(ph1, ph2) == 0
