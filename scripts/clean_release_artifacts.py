from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BAD_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
}
BAD_SUFFIXES = {".pyc", ".pyo"}
BAD_SUFFIX_PATTERNS = (".egg-info",)

removed: list[str] = []

for path in sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True):
    if ".git" in path.parts:
        continue
    rel = path.relative_to(ROOT).as_posix()
    if path.is_dir() and (path.name in BAD_DIR_NAMES or path.name.endswith(BAD_SUFFIX_PATTERNS)):
        shutil.rmtree(path, ignore_errors=True)
        removed.append(rel + "/")
    elif path.is_file() and path.suffix in BAD_SUFFIXES:
        path.unlink(missing_ok=True)
        removed.append(rel)

if removed:
    print("cleaned release artifacts:")
    for item in sorted(removed)[:80]:
        print("-", item)
    if len(removed) > 80:
        print(f"... {len(removed) - 80} more")
else:
    print("cleaned release artifacts: none found")
