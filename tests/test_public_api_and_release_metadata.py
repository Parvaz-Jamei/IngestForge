from __future__ import annotations

import tomllib
from pathlib import Path

from ingestforge import ingest_url, pipeline


def test_simple_public_api_ingest_url(local_server, tmp_path):
    package = ingest_url(
        local_server + "/article",
        runs_dir=tmp_path,
        overrides={
            "fetch": {"deny_private_networks": False},
            "search": {"obey_robots_txt": False},
        },
    )
    assert package.job_id
    assert (tmp_path / package.job_id / "package.json").exists()


def test_simple_public_api_pipeline(local_server, tmp_path):
    pipe = pipeline(
        "profiles/manual_safe.yaml",
        overrides={
            "fetch": {"deny_private_networks": False},
            "search": {"obey_robots_txt": False},
        },
    )
    package = pipe.ingest_url(local_server + "/article", runs_dir=tmp_path)
    assert package.source_refs


def test_python_support_metadata_is_3_11_to_3_14():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert project["requires-python"] == ">=3.11,<3.15"
    classifiers = set(project["classifiers"])
    for version in ["3.11", "3.12", "3.13", "3.14"]:
        assert f"Programming Language :: Python :: {version}" in classifiers
    assert "Programming Language :: Python :: 3.10" not in classifiers


def test_ci_matrix_mentions_all_supported_pythons_and_oses():
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    for version in ["3.11", "3.12", "3.13", "3.14"]:
        assert version in ci
    for os_name in ["ubuntu-latest", "windows-latest", "macos-latest"]:
        assert os_name in ci


def test_builtin_profile_fallback_works_when_source_profiles_missing(monkeypatch):
    from ingestforge.core.config import load_profile

    profile = load_profile("profiles/manual_safe.yaml")
    assert profile.profile_name == "manual_safe"
