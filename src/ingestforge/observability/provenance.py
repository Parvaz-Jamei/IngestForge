from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingestforge.core.contracts import stable_json_hash


class ProvenanceLedger:
    """Append-only provenance-inspired audit ledger.

    This is intentionally described as provenance-inspired rather than fully
    W3C PROV-compatible until formal entity/activity/agent mappings are added.
    """

    def __init__(self, path: Path, *, config_hash: str | None = None) -> None:
        self.path = path
        self.config_hash = config_hash
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        entity: str,
        activity: str,
        agent: str,
        attributes: dict[str, Any] | None = None,
        input_ids: list[str] | None = None,
        output_ids: list[str] | None = None,
        source_url: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        record_id = f"prov_{uuid4().hex[:16]}"
        timestamp = datetime.now(UTC).isoformat()
        record = {
            "event_id": record_id,
            "event_type": activity,
            "timestamp": timestamp,
            "entity": entity,
            "activity": activity,
            "agent": agent,
            "input_ids": input_ids or [],
            "output_ids": output_ids or [],
            "source_url": source_url,
            "provider": provider,
            "model": model,
            "config_hash": self.config_hash,
            "attributes": attributes or {},
        }
        record["sha256"] = stable_json_hash(record)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record_id
