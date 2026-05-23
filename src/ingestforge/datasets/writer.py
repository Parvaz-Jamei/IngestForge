from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ingestforge.core.config import DatasetConfig
from ingestforge.core.contracts import StandardPackage
from ingestforge.datasets.chunker import build_rag_records
from ingestforge.datasets.data_card import write_data_card


class DatasetWriter:
    def __init__(self, runs_dir: Path, config: DatasetConfig | None = None) -> None:
        self.runs_dir = runs_dir
        self.config = config or DatasetConfig()

    def _mkdirs(self, run_dir: Path) -> None:
        required = ["assets", "manifests"]
        if self.config.write_raw:
            required += ["raw/pages", "raw/images", "raw/ocr"]
        if self.config.write_clean:
            required.append("clean")
        if self.config.write_chunks:
            required.append("chunks")
        for sub in required:
            (run_dir / sub).mkdir(parents=True, exist_ok=True)

    def write_package(self, package: StandardPackage) -> Path:
        run_dir = self.runs_dir / package.job_id
        self._mkdirs(run_dir)
        if self.config.write_raw:
            for asset in package.assets:
                if asset.local_path and Path(asset.local_path).is_file():
                    target = run_dir / "raw/images" / Path(asset.local_path).name
                    if Path(asset.local_path) != target:
                        shutil.copy2(asset.local_path, target)
                    asset.export_path = str(target.relative_to(run_dir))
        records = (
            build_rag_records(
                package,
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                chunk_unit=self.config.chunk_unit,
                tokenizer=self.config.tokenizer,
                tokenizer_model=self.config.tokenizer_model,
            )
            if self.config.write_chunks
            else []
        )
        package.dataset_records = records
        package.finalize_hashes()
        (run_dir / "package.json").write_text(package.model_dump_json(indent=2), encoding="utf-8")
        (run_dir / "validation_report.json").write_text(
            package.validation_report.model_dump_json(indent=2), encoding="utf-8"
        )
        (run_dir / "evidence_bundle.json").write_text(
            package.evidence_bundle.model_dump_json(indent=2), encoding="utf-8"
        )
        if self.config.write_clean:
            with (run_dir / "clean/articles.jsonl").open("w", encoding="utf-8") as f:
                f.write(
                    json.dumps(package.article.model_dump(mode="json"), ensure_ascii=False) + "\n"
                )
        if self.config.write_chunks:
            with (run_dir / "chunks/rag_chunks.jsonl").open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(
                        json.dumps(r.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                        + "\n"
                    )
        if self.config.write_manifests:
            source_manifest = [s.model_dump(mode="json") for s in package.source_refs]
            (run_dir / "manifests/source_manifest.json").write_text(
                json.dumps(source_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            dataset_manifest: dict[str, Any] = {
                "job_id": package.job_id,
                "package_schema": package.schema_version,
                "source_count": len(package.source_refs),
                "asset_count": len(package.assets),
                "chunk_count": len(records) if self.config.write_chunks else 0,
                "evidence_bundle_hash": package.evidence_bundle_hash,
                "package_hash": package.package_hash,
                "dataset_flags": self.config.model_dump(mode="json"),
                "tokenizer": self.config.tokenizer,
                "chunk_unit": self.config.chunk_unit,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
            }
            (run_dir / "manifests/dataset_manifest.json").write_text(
                json.dumps(dataset_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        if self.config.write_data_card:
            write_data_card(package, run_dir)
        return run_dir
