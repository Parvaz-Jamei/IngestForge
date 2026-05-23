from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

try:
    __version__ = version("ingestforge")
except PackageNotFoundError:
    __version__ = "0.4.0a6"

from ingestforge.core.config import IngestForgeProfile, load_profile
from ingestforge.core.contracts import StandardPackage
from ingestforge.core.pipeline import IngestPipeline


def pipeline(
    profile: str | Path | IngestForgeProfile = "profiles/manual_safe.yaml",
    *,
    overrides: dict[str, Any] | None = None,
) -> IngestPipeline:
    """Create an :class:`IngestPipeline` from a profile path or profile object.

    This is the shortest stable public API for library users who do not need to
    manually instantiate the pipeline class.
    """
    loaded = (
        profile
        if isinstance(profile, IngestForgeProfile)
        else load_profile(profile, overrides=overrides)
    )
    return IngestPipeline.from_profile(loaded)


def ingest_url(
    url: str,
    profile: str | Path | IngestForgeProfile = "profiles/manual_safe.yaml",
    *,
    runs_dir: str | Path = "runs",
    dry_run: bool | None = None,
    write_dataset: bool | None = None,
    external_calls: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> StandardPackage:
    """Ingest one URL and return a validated standard package.

    Python callers can explicitly disable writing with ``write_dataset=False``.
    CLI profiles may still write by default.
    """
    return pipeline(profile, overrides=overrides).ingest_url(
        url,
        dry_run=dry_run,
        runs_dir=runs_dir,
        write_dataset=write_dataset,
        external_calls=external_calls,
    )


__all__ = [
    "IngestPipeline",
    "IngestForgeProfile",
    "StandardPackage",
    "ingest_url",
    "load_profile",
    "pipeline",
    "__version__",
]
