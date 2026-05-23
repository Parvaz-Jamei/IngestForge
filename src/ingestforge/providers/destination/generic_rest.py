from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from ingestforge.core.config import DestinationConfig, EndpointConfig
from ingestforge.core.contracts import AssetRecord, SourceRef, StandardPackage
from ingestforge.core.errors import DestinationError
from ingestforge.providers.destination.base import DestinationAdapter
from ingestforge.security.redaction import redact_secrets

TEMPLATE = re.compile(r"^\s*\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}\s*$")


def get_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def set_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    cur: dict[str, Any] = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        child = cur.setdefault(part, {})
        if not isinstance(child, dict):
            raise DestinationError(f"field_map target conflict at {dotted}")
        cur = child
    cur[parts[-1]] = value


def _extract_mapped(data: dict[str, Any], mapping: dict[str, str], key: str) -> Any:
    dotted = mapping.get(key, "")
    return get_path(data, dotted) if dotted else None


class GenericRestDestination(DestinationAdapter):
    """Configurable brand-neutral REST destination adapter."""

    def __init__(self, config: DestinationConfig) -> None:
        self.config = config

    def _template_context(self, package: StandardPackage) -> dict[str, Any]:
        return {
            "article": package.article.model_dump(mode="json"),
            "package": package.model_dump(mode="json"),
        }

    def _render_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            match = TEMPLATE.match(value)
            if match:
                resolved = get_path(context, match.group(1))
                if resolved is None:
                    raise DestinationError(f"undefined payload template variable: {match.group(1)}")
                return resolved
            return value
        if isinstance(value, dict):
            return {k: self._render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(v, context) for v in value]
        return value

    def build_payload(
        self, package: StandardPackage, operation: str = "create_content"
    ) -> dict[str, Any]:
        context = self._template_context(package)
        template = self.config.payload_templates.get(operation)
        if template:
            rendered = self._render_value(template, context)
            if not isinstance(rendered, dict):
                raise DestinationError("payload template must render to an object")
            return rendered
        payload: dict[str, Any] = {}
        if self.config.field_map:
            for source, target in self.config.field_map.items():
                value = get_path(context, source)
                if value is not None:
                    set_path(payload, target, value)
        else:
            payload = package.model_dump(mode="json")
        return payload

    def _headers(
        self, package: StandardPackage | None = None, operation: str = "create_content"
    ) -> dict[str, str]:
        token = os.getenv(self.config.auth.token_env or "") if self.config.auth.token_env else None
        headers: dict[str, str] = {}
        if token and self.config.auth.mode in {
            "bearer",
            "bearer_token",
            "bearer_with_optional_csrf",
            "bearer_with_csrf",
        }:
            headers["Authorization"] = f"Bearer {token}"
        if package and self.config.idempotency.enabled:
            key = hashlib.sha256(
                f"{package.job_id}:{self.config.provider}:{operation}".encode()
            ).hexdigest()
            headers[self.config.idempotency.header] = key
        return headers

    def _endpoint(self, name: str, required: bool = False) -> EndpointConfig | None:
        endpoint = self.config.endpoints.get(name)
        if required and not endpoint:
            raise DestinationError(f"{name} endpoint is required")
        return endpoint

    def _url(self, endpoint: EndpointConfig, **values: Any) -> str:
        if not self.config.base_url:
            raise DestinationError("generic_rest destination requires base_url")
        return self.config.base_url.rstrip("/") + endpoint.path.format(**values)

    def _request(
        self,
        client: httpx.Client,
        endpoint: EndpointConfig,
        *,
        headers: dict[str, str],
        values: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self._url(endpoint, **(values or {}))
        last_error: Exception | None = None
        for attempt in range(self.config.retry.attempts):
            try:
                response = client.request(
                    endpoint.method,
                    url,
                    json=json_payload if not files else None,
                    files=files,
                    data=data,
                    headers=headers,
                )
                if (
                    response.status_code in {408, 429, 500, 502, 503, 504}
                    and attempt + 1 < self.config.retry.attempts
                ):
                    time.sleep(self.config.retry.backoff_seconds)
                    continue
                if response.status_code >= 400:
                    raise DestinationError(f"destination failed: {response.status_code} {url}")
                parsed = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {"text": response.text}
                )
                csrf = response.headers.get("x-csrf-token") or response.headers.get("X-CSRF-Token")
                if csrf:
                    headers["X-CSRF-Token"] = csrf
                return parsed
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= self.config.retry.attempts:
                    break
                time.sleep(self.config.retry.backoff_seconds)
        raise DestinationError(str(last_error) if last_error else "destination request failed")

    def _build_source_payload(self, content_id: Any, source: SourceRef) -> dict[str, Any]:
        payload = source.model_dump(mode="json")
        payload["content_id"] = content_id
        return payload

    def _build_asset_data(self, content_id: Any, asset: AssetRecord) -> dict[str, Any]:
        return {
            "content_id": str(content_id),
            "asset_id": asset.asset_id,
            "source_url": asset.source_url or "",
            "normalized_url_hash": asset.normalized_url_hash or "",
            "sha256": asset.sha256 or "",
            "content_hash_prefix": asset.content_hash_prefix or "",
            "perceptual_hash": asset.perceptual_hash or "",
            "mime_type": asset.mime_type or "",
            "width": str(asset.width or ""),
            "height": str(asset.height or ""),
            "license_status": asset.license_status,
            "caption": asset.caption or "",
        }

    def publish(self, package: StandardPackage) -> dict[str, Any]:
        create_endpoint = self._endpoint("create_content", required=True)
        assert create_endpoint is not None
        headers = self._headers(package)
        result: dict[str, Any] = {
            "ok": True,
            "steps": [],
            "content_id": None,
            "asset_receipts": [],
            "source_receipts": [],
            "verify_result": None,
            "errors": [],
            "source_ref_count": 0,
            "asset_count": 0,
        }
        receipts: list[dict[str, Any]] = []
        with httpx.Client(timeout=30) as client:
            bootstrap = self._endpoint("csrf_bootstrap")
            if bootstrap:
                response = self._request(client, bootstrap, headers=headers)
                receipts.append(
                    {
                        "operation": "csrf_bootstrap",
                        "ok": True,
                        "response": redact_secrets(json.dumps(response)),
                    }
                )
            create_response = self._request(
                client,
                create_endpoint,
                headers=headers,
                json_payload=self.build_payload(package, "create_content"),
            )
            receipts.append(
                {
                    "operation": "create_content",
                    "ok": True,
                    "response": redact_secrets(json.dumps(create_response)),
                }
            )
            content_id = _extract_mapped(
                create_response, self.config.response_map.get("create_content", {}), "content_id"
            )
            if content_id is None:
                content_id = get_path(create_response, "data.content.id") or get_path(
                    create_response, "content_id"
                )
            if content_id is None and any(
                self._endpoint(name) for name in ["source_ref", "upload_asset", "verify"]
            ):
                raise DestinationError("create_content did not return required content_id")
            result["content_id"] = content_id
            source_endpoint = self._endpoint("source_ref")
            if source_endpoint and content_id is not None:
                for source in package.source_refs:
                    response = self._request(
                        client,
                        source_endpoint,
                        headers=headers,
                        json_payload=self._build_source_payload(content_id, source),
                        values={"content_id": content_id},
                    )
                    result["source_receipts"].append(response)
                    result["source_ref_count"] += 1
                    receipts.append(
                        {
                            "operation": "source_ref",
                            "ok": True,
                            "response": redact_secrets(json.dumps(response)),
                        }
                    )
            upload_endpoint = self._endpoint("upload_asset")
            if upload_endpoint and content_id is not None:
                for asset in package.assets:
                    if not asset.local_path or not Path(asset.local_path).is_file():
                        continue
                    data = self._build_asset_data(content_id, asset)
                    if upload_endpoint.content_type == "multipart":
                        with Path(asset.local_path).open("rb") as fh:
                            files = {
                                "file": (
                                    Path(asset.local_path).name,
                                    fh,
                                    asset.mime_type or "application/octet-stream",
                                )
                            }
                            response = self._request(
                                client,
                                upload_endpoint,
                                headers=headers,
                                files=files,
                                data=data,
                                values={"content_id": content_id},
                            )
                    else:
                        response = self._request(
                            client,
                            upload_endpoint,
                            headers=headers,
                            json_payload=data,
                            values={"content_id": content_id},
                        )
                    result["asset_receipts"].append(response)
                    result["asset_count"] += 1
                    receipts.append(
                        {
                            "operation": "upload_asset",
                            "ok": True,
                            "response": redact_secrets(json.dumps(response)),
                        }
                    )
            verify_endpoint = self._endpoint("verify")
            if verify_endpoint and content_id is not None:
                verify_response = self._request(
                    client, verify_endpoint, headers=headers, values={"content_id": content_id}
                )
                result["verify_result"] = verify_response
                receipts.append(
                    {
                        "operation": "verify",
                        "ok": True,
                        "response": redact_secrets(json.dumps(verify_response)),
                    }
                )
        result["steps"] = receipts
        return result
