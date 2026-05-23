from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def content_hash_prefix(path: str | Path, length: int = 16) -> str:
    return file_sha256(path)[:length]


def perceptual_hash_or_none(path: str | Path) -> str | None:
    try:
        from PIL import Image

        img = Image.open(path).convert("L").resize((8, 8))
        values = list(img.getdata())
        avg = sum(values) / len(values)
        bits = "".join("1" if v > avg else "0" for v in values)
        return f"{int(bits, 2):016x}"
    except Exception:
        return None
