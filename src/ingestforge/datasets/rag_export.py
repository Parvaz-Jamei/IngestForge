from __future__ import annotations

import json
from pathlib import Path


def export_jsonl(run_dir: str | Path, out_path: str | Path | None = None) -> Path:
    run_dir = Path(run_dir)
    chunks = run_dir / "chunks/rag_chunks.jsonl"
    if out_path is None:
        out_path = run_dir / "rag_export.jsonl"
    out_path = Path(out_path)
    with chunks.open(encoding="utf-8") as src, out_path.open("w", encoding="utf-8") as dst:
        for line in src:
            obj = json.loads(line)
            dst.write(
                json.dumps(
                    {
                        "id": obj["record_id"],
                        "text": obj["text"],
                        "metadata": {k: v for k, v in obj.items() if k not in {"text"}},
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    return out_path
