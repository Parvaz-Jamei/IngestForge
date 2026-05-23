from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import ingestforge.providers.ai  # noqa: F401
import ingestforge.providers.destination  # noqa: F401
import ingestforge.providers.search  # noqa: F401
from ingestforge.core.config import (
    IngestForgeProfile,
    config_sha256,
    load_profile,
    write_resolved_profile,
)
from ingestforge.core.contracts import (
    ArticleObject,
    AssetRecord,
    EvidenceBundle,
    MultilingualText,
    SourceRef,
    StandardPackage,
    stable_json_hash,
)
from ingestforge.core.errors import ConfigError
from ingestforge.core.registry import registry
from ingestforge.core.validation import corrective_retrieval_gate, reflection_gate
from ingestforge.observability.provenance import ProvenanceLedger
from ingestforge.observability.run_manifest import write_manifest
from ingestforge.providers.fetch.fetcher import SafeFetcher
from ingestforge.providers.fetch.html_extractor import HtmlExtractor
from ingestforge.providers.fetch.safe_url import host_allowed, normalize_url, validate_public_url
from ingestforge.providers.media.downloader import MediaDownloader
from ingestforge.providers.media.image_candidates import discover_image_urls
from ingestforge.providers.media.ocr import ocr_provider
from ingestforge.providers.media.vision_ranker import vision_ranker
from ingestforge.providers.search.base import SearchQuery


class IngestPipeline:
    def __init__(self, profile: IngestForgeProfile) -> None:
        self.profile = profile

    @classmethod
    def from_profile(cls, profile: IngestForgeProfile | str | Path) -> IngestPipeline:
        if not isinstance(profile, IngestForgeProfile):
            profile = load_profile(profile)
        return cls(profile)

    def _ai_provider(self):
        cls = registry.get_ai(self.profile.ai.provider)
        return cls(
            model=self.profile.ai.model,
            temperature=self.profile.ai.temperature,
            max_output_tokens=self.profile.ai.max_output_tokens,
            max_input_chars=self.profile.ai.max_input_chars_per_request,
            thinking_enabled=self.profile.ai.thinking.enabled,
            api_style=self.profile.ai.api_style,
            source_language=self.profile.ai.source_language,
            target_languages=self.profile.ai.target_languages,
        )

    def _external_ai_allowed(self, override: str | None = None) -> bool:
        mode = override or self.profile.pipeline.external_calls
        if mode == "profile":
            mode = self.profile.pipeline.external_calls
        if self.profile.ai.provider == "mock":
            return True
        return mode in {"ai_only", "enabled"}

    def _external_search_allowed(self, override: str | None = None) -> bool:
        mode = override or self.profile.pipeline.external_calls
        if self.profile.search.provider == "manual":
            return True
        return mode in {"search_only", "enabled"}

    def _allowed_url(self, url: str) -> str:
        safe = validate_public_url(
            url,
            deny_private_networks=self.profile.fetch.deny_private_networks,
            require_https=self.profile.fetch.require_https,
        )
        if (
            self.profile.fetch.ssrf_mode == "strict_allowlist"
            and not self.profile.search.allowed_domains
        ):
            raise ConfigError("strict_allowlist SSRF mode requires search.allowed_domains")
        if not host_allowed(
            safe,
            self.profile.search.allowed_domains,
            self.profile.search.denied_domains,
            self.profile.search.allow_subdomains,
        ):
            raise ValueError("URL is not allowed by domain policy")
        return safe

    def _fallback_article(self, evidence: EvidenceBundle) -> ArticleObject:
        title = evidence.page_title or "Ingested content package"
        body = evidence.clean_text[:4000]
        desc = "Generated locally without external AI calls; review required."
        return ArticleObject(
            title=MultilingualText.from_languages(self.profile.ai.target_languages, title),
            description=MultilingualText.from_languages(self.profile.ai.target_languages, desc),
            body=MultilingualText.from_languages(self.profile.ai.target_languages, body),
            tags=["needs-review"],
        )

    def ingest_url(
        self,
        url: str,
        *,
        dry_run: bool | None = None,
        runs_dir: str | Path = "runs",
        write_dataset: bool | None = None,
        external_calls: str | None = None,
    ) -> StandardPackage:
        cfg_hash = config_sha256(self.profile)
        effective_dry_run = self.profile.pipeline.dry_run if dry_run is None else dry_run
        write_dataset_output = (
            self.profile.pipeline.write_dataset if write_dataset is None else write_dataset
        )
        mode = self.profile.pipeline.mode
        initial_url = self._allowed_url(url)

        if mode == "validate_only":
            norm = normalize_url(initial_url)
            source = SourceRef(
                url=initial_url,
                normalized_url=norm,
                source_hash=stable_json_hash(norm),
                source_domain=urlparse(norm).hostname,
                license_status="needs_review",
                extraction_method="url_validation_only",
            )
            package = StandardPackage(source_refs=[source])
            package.destination_plan.dry_run = True
            package.destination_plan.provider = self.profile.destination.provider
            reflection_gate(package, allow_weak_claims=self.profile.gates.allow_weak_claims)
            if write_dataset_output:
                package.write_dataset(runs_dir, config=self.profile.dataset)
            return package

        fetcher = SafeFetcher(self.profile.fetch, self.profile.search)
        fetched = fetcher.fetch_html(initial_url)
        extracted = HtmlExtractor(self.profile.extraction).extract(
            fetched.text, url=fetched.final_url
        )
        norm = normalize_url(fetched.final_url)
        clean_len = len(extracted.clean_text)
        source = SourceRef(
            url=fetched.final_url,
            normalized_url=norm,
            source_hash=stable_json_hash(norm),
            source_domain=urlparse(norm).hostname,
            title=extracted.title,
            license_status="needs_review",
            robots_allowed=fetched.robots_allowed,
            extraction_method=str(extracted.diagnostics.get("backend") or "html_extractor"),
            source_quality_score=min(clean_len / 3000, 1.0),
            extraction_quality_score=min(
                clean_len / max(self.profile.gates.min_clean_text_chars, 1), 1.0
            ),
            source_risk_flags=[] if clean_len else ["empty_extraction"],
        )
        evidence = EvidenceBundle(
            page_title=extracted.title,
            source_refs=[source],
            clean_text=extracted.clean_text,
            selected_snippets=extracted.snippets[:10],
            provider_id=self.profile.ai.provider,
            model_id=self.profile.ai.model,
            prompt_version=self.profile.ai.prompt_version,
        )
        gate = corrective_retrieval_gate(evidence, self.profile.gates)
        package = StandardPackage(source_refs=[source], evidence_bundle=evidence)
        run_dir = Path(runs_dir) / package.job_id
        ledger: ProvenanceLedger | None = None
        prov_fetch: str | None = None
        if write_dataset_output:
            run_dir.mkdir(parents=True, exist_ok=True)
            write_resolved_profile(self.profile, run_dir)
            ledger = ProvenanceLedger(run_dir / "provenance.jsonl", config_hash=cfg_hash)
            prov_fetch = ledger.append(
                entity=fetched.final_url,
                activity="fetch_html",
                agent="ingestforge.fetcher",
                attributes={
                    "bytes_read": fetched.bytes_read,
                    "status_code": fetched.status_code,
                    "encoding_used": fetched.encoding_used,
                    "decode_replacement_count": fetched.decode_replacement_count,
                },
                source_url=fetched.final_url,
            )
            package.provenance[prov_fetch] = {"activity": "fetch_html", "entity": fetched.final_url}

        if write_dataset_output:
            image_urls = discover_image_urls(fetched.text, fetched.final_url)[
                : self.profile.media.max_images_per_job
            ]
            downloader = MediaDownloader(
                self.profile.fetch, self.profile.media, self.profile.search
            )
            ranker = (
                vision_ranker(self.profile.vision.provider)
                if self.profile.media.use_vision_ranker
                else None
            )
            ocr = ocr_provider(self.profile.ocr.provider) if self.profile.media.use_ocr else None
            assets: list[AssetRecord] = []
            media_dir = run_dir / "assets"
            for image_url in image_urls:
                try:
                    media = downloader.download(image_url, media_dir)
                    vision = None
                    if ranker:
                        vision = ranker.rank(filename=media.local_path.name)
                        if (
                            float(vision.get("quality_score", 0.0))
                            < self.profile.vision.min_quality_score
                        ):
                            evidence.source_risk_flags.append("image_rejected_by_vision_gate")
                            continue
                    ocr_result = None
                    if ocr:
                        ocr_result = ocr.extract_text(media.local_path, self.profile.ocr.languages)
                        if ocr_result.text:
                            evidence.ocr_excerpts.append(ocr_result.text[:2000])
                    asset = AssetRecord(
                        source_url=media.source_url,
                        normalized_url_hash=stable_json_hash(media.source_url),
                        local_path=str(media.local_path),
                        export_path=f"assets/{media.local_path.name}",
                        sha256=media.sha256,
                        content_hash_prefix=media.content_hash_prefix,
                        perceptual_hash=media.perceptual_hash,
                        mime_type=media.mime_type,
                        width=media.width,
                        height=media.height,
                        ocr_text=ocr_result.text[:4000] if ocr_result and ocr_result.text else None,
                        ocr_confidence=ocr_result.confidence if ocr_result else None,
                        ocr_status=ocr_result.status if ocr_result else "disabled",
                        vision_result=vision,
                        license_status="needs_review",
                    )
                    assets.append(asset)
                    if ledger and prov_fetch:
                        ledger.append(
                            entity=asset.asset_id,
                            activity="download_asset",
                            agent="ingestforge.media",
                            attributes={
                                "sha256": asset.sha256,
                                "width": asset.width,
                                "height": asset.height,
                            },
                            source_url=media.source_url,
                            input_ids=[prov_fetch],
                            output_ids=[asset.asset_id],
                        )
                except Exception as exc:
                    evidence.source_risk_flags.append(f"image_download_failed:{type(exc).__name__}")
            evidence.selected_image_observations = [a.model_dump(mode="json") for a in assets]
            package.assets = assets

        package.validation_report = gate
        if gate.can_generate:
            if self._external_ai_allowed(external_calls):
                article = self._ai_provider().build_article(
                    evidence, schema={"type": "object", "properties": {}}
                )
                package.article = article
                if ledger:
                    ledger.append(
                        entity=package.job_id,
                        activity="ai_generate",
                        agent="ingestforge.ai",
                        attributes={
                            "provider": self.profile.ai.provider,
                            "model": self.profile.ai.model,
                            "external_calls": external_calls
                            or self.profile.pipeline.external_calls,
                        },
                        provider=self.profile.ai.provider,
                        model=self.profile.ai.model,
                    )
            else:
                package.article = self._fallback_article(evidence)
                package.validation_report.warnings.append(
                    "ai_external_calls_disabled_local_article_used"
                )

        package.destination_plan.dry_run = effective_dry_run
        package.destination_plan.provider = self.profile.destination.provider
        reflection_gate(package, allow_weak_claims=self.profile.gates.allow_weak_claims)
        if write_dataset_output:
            package.write_dataset(runs_dir, config=self.profile.dataset)
            write_manifest(
                run_dir / "run_manifest.json",
                {
                    "job_id": package.job_id,
                    "profile_name": self.profile.profile_name,
                    "resolved_profile_sha256": cfg_hash,
                    "package_hash": package.package_hash,
                    "provider": self.profile.ai.provider,
                    "model": self.profile.ai.model,
                    "pipeline_mode": mode,
                    "dry_run": effective_dry_run,
                    "external_calls": external_calls or self.profile.pipeline.external_calls,
                },
            )
        else:
            package.finalize_hashes()
        return package

    def search_topic(
        self, query: str, *, max_results: int | None = None, external_calls: str | None = None
    ) -> list[str]:
        if not self._external_search_allowed(external_calls):
            raise ConfigError("external search calls are disabled by profile")
        cls = registry.get_search(self.profile.search.provider)
        provider = cls()
        search_query = SearchQuery(
            query=query,
            max_results=max_results or self.profile.search.max_results,
            allowed_domains=self.profile.search.allowed_domains,
            denied_domains=self.profile.search.denied_domains,
        )
        results = provider.search(search_query)
        urls: list[str] = []
        seen: set[str] = set()
        for result in results:
            try:
                safe = self._allowed_url(result.url)
            except Exception:
                continue
            if safe not in seen:
                urls.append(safe)
                seen.add(safe)
        return urls


def pipeline(profile: IngestForgeProfile | str | Path | None = None) -> IngestPipeline:
    return IngestPipeline.from_profile(profile or "manual_safe.yaml")


def ingest_url(
    url: str,
    *,
    profile: IngestForgeProfile | str | Path | None = None,
    runs_dir: str | Path = "runs",
    write_dataset: bool | None = None,
    external_calls: str | None = None,
) -> StandardPackage:
    return pipeline(profile).ingest_url(
        url,
        runs_dir=runs_dir,
        write_dataset=write_dataset,
        external_calls=external_calls,
    )
