from typer.testing import CliRunner

from ingestforge.cli import app
from ingestforge.core.config import load_profile
from ingestforge.core.pipeline import IngestPipeline

runner = CliRunner()


def test_cli_version():
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0 and "0.4.0" in res.output


def test_cli_validate_profile():
    res = runner.invoke(app, ["validate-profile", "profiles/manual_safe.yaml"])
    assert res.exit_code == 0 and "manual_safe" in res.output


def test_pipeline_ingest_local(local_server, tmp_path):
    p = load_profile(
        "profiles/manual_safe.yaml",
        overrides={"fetch": {"deny_private_networks": False}, "search": {"obey_robots_txt": False}},
    )
    package = IngestPipeline.from_profile(p).ingest_url(
        local_server + "/article", runs_dir=tmp_path
    )
    assert package.source_refs and (tmp_path / package.job_id / "package.json").exists()


def test_search_topic_manual_filters():
    p = load_profile(
        "profiles/manual_safe.yaml",
        overrides={
            "fetch": {"deny_private_networks": False},
            "search": {"provider": "manual", "allowed_domains": ["example.com"]},
        },
    )
    urls = IngestPipeline.from_profile(p).search_topic("https://example.com/a https://other.com/b")
    assert urls == ["https://example.com/a"]
