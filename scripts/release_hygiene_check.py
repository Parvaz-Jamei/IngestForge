from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TREE_MODE = "--source-tree" in sys.argv
BAD_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "build", "dist"}
BAD_SUFFIXES = {".pyc", ".pyo"}
LEGACY_PATTERNS = ["power" + "lc", "private" + "_app", "content" + "-review", "service" + "-token"]
SECRET_PATTERNS = [r"sk-[A-Za-z0-9_-]{20,}", r"svc_[A-Za-z0-9_-]{20,}", r"AIza[A-Za-z0-9_-]{20,}"]
ABS_PATH_PATTERNS = ["/mnt" + "/data/", "/home" + r"/[^\s]+", "C:" + r"\\Users\\"]

errors: list[str] = []
for path in ROOT.rglob("*"):
    rel = path.relative_to(ROOT).as_posix()
    if ".git" in path.parts:
        continue
    if path.name == ".env.example":
        continue
    # In source-tree mode this script is intentionally runnable after local
    # lint/test/build commands. Generated caches and build outputs are checked
    # by archive/package hygiene separately, so they are skipped here instead
    # of making the acceptance command order brittle. The clean source ZIP
    # creation step still excludes these paths.
    if SOURCE_TREE_MODE and any(part in BAD_DIRS for part in path.parts):
        continue
    if path.name == ".env" or any(part in BAD_DIRS for part in path.parts):
        errors.append(f"forbidden artifact: {rel}")
    if path.suffix in BAD_SUFFIXES:
        errors.append(f"bytecode artifact: {rel}")
    if path.is_file() and path.suffix.lower() in {
        ".py",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".cff",
    }:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LEGACY_PATTERNS:
            if re.search(pattern, text, flags=re.I):
                errors.append(f"legacy/private string {pattern!r}: {rel}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"secret-like token {pattern!r}: {rel}")
        for pattern in ABS_PATH_PATTERNS:
            if re.search(pattern, text):
                errors.append(f"absolute local path {pattern!r}: {rel}")

if errors:
    print("Release hygiene failed:")
    for err in errors[:80]:
        print("-", err)
    if len(errors) > 80:
        print(f"... {len(errors) - 80} more")
    sys.exit(1)

print("release hygiene: PASS")
