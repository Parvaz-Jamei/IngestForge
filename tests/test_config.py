from ingestforge.core.config import load_profile


def test_load_profile():
    p = load_profile("profiles/manual_safe.yaml")
    assert p.profile_name == "manual_safe"


def test_env_precedence(monkeypatch):
    monkeypatch.setenv("INGESTFORGE__AI__PROVIDER", "mock")
    p = load_profile("profiles/strict_industrial.yaml")
    assert p.ai.provider == "mock"


def test_env_expansion(monkeypatch, tmp_path):
    monkeypatch.setenv("DESTINATION_BASE_URL", "https://example.test")
    p = load_profile("profiles/destination_example.yaml")
    assert p.destination.base_url == "https://example.test"
