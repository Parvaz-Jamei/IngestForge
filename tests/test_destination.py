from ingestforge.core.config import DestinationConfig
from ingestforge.core.contracts import ArticleObject, MultilingualText, StandardPackage
from ingestforge.providers.destination.generic_rest import GenericRestDestination
from ingestforge.providers.destination.local_export import LocalExportDestination


def test_generic_rest_payload_mapping():
    cfg = DestinationConfig(provider="generic_rest", field_map={"article.title.en": "title"})
    p = StandardPackage(article=ArticleObject(title=MultilingualText(en="Hello")))
    payload = GenericRestDestination(cfg).build_payload(p)
    assert payload["title"] == "Hello"


def test_local_export(tmp_path):
    p = StandardPackage(
        article=ArticleObject(title=MultilingualText(en="Hello"), body=MultilingualText(en="Body"))
    )
    res = LocalExportDestination(tmp_path).publish(p)
    assert res["ok"]


def test_generic_rest_full_sequence_with_source_and_asset(tmp_path, monkeypatch):
    from ingestforge.core.config import DestinationAuthConfig, EndpointConfig
    from ingestforge.core.contracts import AssetRecord, SourceRef

    asset_path = tmp_path / "image.jpg"
    asset_path.write_bytes(b"fake image bytes")
    package = StandardPackage(
        article=ArticleObject(title=MultilingualText(en="Hello"), body=MultilingualText(en="Body")),
        source_refs=[
            SourceRef(url="https://example.com/a", normalized_url="https://example.com/a")
        ],
        assets=[
            AssetRecord(
                local_path=str(asset_path),
                source_url="https://example.com/i.jpg",
                mime_type="image/jpeg",
            )
        ],
    )
    cfg = DestinationConfig(
        provider="generic_rest",
        base_url="https://dest.example",
        auth=DestinationAuthConfig(mode="bearer_with_optional_csrf", token_env="DEST_TOKEN"),
        endpoints={
            "csrf_bootstrap": EndpointConfig(method="GET", path="/csrf"),
            "create_content": EndpointConfig(method="POST", path="/content"),
            "source_ref": EndpointConfig(method="POST", path="/source"),
            "upload_asset": EndpointConfig(method="POST", path="/upload", content_type="multipart"),
            "verify": EndpointConfig(method="GET", path="/content/{content_id}"),
        },
        response_map={"create_content": {"content_id": "data.content.id"}},
    )
    calls = []

    class FakeResponse:
        def __init__(self, data, headers=None, status_code=200):
            self._data = data
            self.headers = headers or {"content-type": "application/json"}
            self.status_code = status_code
            self.text = "ok"

        def json(self):
            return self._data

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/csrf"):
                return FakeResponse(
                    {"ok": True},
                    headers={"content-type": "application/json", "x-csrf-token": "csrf"},
                )
            if url.endswith("/content") and method == "POST":
                return FakeResponse({"data": {"content": {"id": 123}}})
            if url.endswith("/source"):
                return FakeResponse({"ok": True, "data": {"source_ref": {"id": 4}}})
            if url.endswith("/upload"):
                return FakeResponse({"ok": True, "data": {"asset": {"id": 5}}})
            if url.endswith("/content/123"):
                return FakeResponse({"ok": True, "data": {"content": {"id": 123}}})
            raise AssertionError(url)

    monkeypatch.setenv("DEST_TOKEN", "token")
    monkeypatch.setattr("ingestforge.providers.destination.generic_rest.httpx.Client", FakeClient)
    result = GenericRestDestination(cfg).publish(package)
    assert result["ok"] is True
    assert result["content_id"] == 123
    assert result["source_ref_count"] == 1
    assert result["asset_count"] == 1
    assert [c[0] for c in calls] == ["GET", "POST", "POST", "POST", "GET"]
    assert calls[1][2]["headers"]["Authorization"] == "Bearer token"
    assert calls[1][2]["headers"]["X-CSRF-Token"] == "csrf"
