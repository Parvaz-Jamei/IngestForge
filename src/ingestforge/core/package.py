from __future__ import annotations

from pathlib import Path

from ingestforge.core.contracts import StandardPackage


def read_package(path: str | Path) -> StandardPackage:
    return StandardPackage.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_package(package: StandardPackage, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    return p
