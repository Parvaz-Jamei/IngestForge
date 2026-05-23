from __future__ import annotations

from pathlib import Path

from ingestforge.core.contracts import StandardPackage
from ingestforge.providers.destination.base import DestinationAdapter


class LocalExportDestination(DestinationAdapter):
    def __init__(self, runs_dir: str | Path = "runs") -> None:
        self.runs_dir = Path(runs_dir)

    def publish(self, package: StandardPackage) -> dict:
        run_dir = package.write_dataset(self.runs_dir)
        return {"ok": True, "provider": "local_export", "run_dir": str(run_dir)}
