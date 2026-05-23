from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path

import typer

from ingestforge import __version__
from ingestforge.core.config import load_profile, validate_profile
from ingestforge.core.package import read_package
from ingestforge.core.pipeline import IngestPipeline
from ingestforge.core.provider_doctor import run_provider_doctor
from ingestforge.datasets.rag_export import export_jsonl
from ingestforge.providers.destination.generic_rest import GenericRestDestination
from ingestforge.providers.destination.local_export import LocalExportDestination

app = typer.Typer(help="Config-driven AI content ingestion and RAG dataset library.")
doctor_app = typer.Typer(help="Local and optional live diagnostics for provider configuration.")
DEFAULT_PROFILE_ARG = typer.Argument(Path("profiles/manual_safe.yaml"))
DEFAULT_PROFILE_OPT = typer.Option(Path("profiles/manual_safe.yaml"))
DESTINATION_PROFILE_OPT = typer.Option(Path("profiles/destination_example.yaml"))


@app.command()
def init(target: Path = DEFAULT_PROFILE_ARG):
    """Create a starter profile file for a new project."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        text = (resources.files("ingestforge.profiles") / "manual_safe.yaml").read_text(
            encoding="utf-8"
        )
        target.write_text(text, encoding="utf-8")
        created = True
    else:
        created = False
    typer.echo(
        json.dumps(
            {
                "version": __version__,
                "profile": str(target),
                "created": created,
                "next": f"ingestforge ingest-url https://example.com/article --profile {target}",
            },
            indent=2,
        )
    )


@app.command("validate-profile")
def validate_profile_cmd(profile: Path):
    p = validate_profile(profile)
    typer.echo(p.model_dump_json(indent=2))


@app.command("ingest-url")
def ingest_url(
    url: str,
    profile: Path = DEFAULT_PROFILE_OPT,
    dry_run: bool = True,
    runs_dir: Path = Path("runs"),
    no_external_calls: bool = typer.Option(
        False, "--no-external-calls", help="Disable all external AI/search calls for this run."
    ),
    external_calls: str | None = typer.Option(None, "--external-calls"),
    live: bool = typer.Option(
        False, "--live", help="Enable live external calls according to the profile."
    ),
    no_live: bool = typer.Option(False, "--no-live", help="Force external calls to disabled."),
    write_dataset: bool = True,
):
    effective_external_calls = external_calls
    if no_external_calls or no_live:
        effective_external_calls = "disabled"
    elif live:
        effective_external_calls = "enabled"
    pipeline_overrides: dict[str, object] = {"dry_run": dry_run, "write_dataset": write_dataset}
    if effective_external_calls is not None:
        pipeline_overrides["external_calls"] = effective_external_calls
    p = load_profile(
        profile,
        overrides={"pipeline": pipeline_overrides},
    )
    package = IngestPipeline.from_profile(p).ingest_url(
        url,
        dry_run=dry_run,
        runs_dir=runs_dir,
        write_dataset=write_dataset,
        external_calls=effective_external_calls,
    )
    typer.echo(
        json.dumps(
            {
                "job_id": package.job_id,
                "package": str(runs_dir / package.job_id / "package.json"),
                "valid": package.validation_report.is_valid,
            },
            indent=2,
        )
    )


@app.command("search-topic")
def search_topic(
    query: str,
    profile: Path = DEFAULT_PROFILE_OPT,
    dry_run: bool = True,
    no_external_calls: bool = typer.Option(
        False, "--no-external-calls", help="Disable all external AI/search calls for this run."
    ),
    external_calls: str | None = typer.Option(None, "--external-calls"),
    live: bool = typer.Option(
        False, "--live", help="Enable live external calls according to the profile."
    ),
    no_live: bool = typer.Option(False, "--no-live", help="Force external calls to disabled."),
):
    effective_external_calls = external_calls
    if no_external_calls or no_live:
        effective_external_calls = "disabled"
    elif live:
        effective_external_calls = "enabled"
    pipeline_overrides: dict[str, object] = {"dry_run": dry_run}
    if effective_external_calls is not None:
        pipeline_overrides["external_calls"] = effective_external_calls
    p = load_profile(profile, overrides={"pipeline": pipeline_overrides})
    urls = IngestPipeline.from_profile(p).search_topic(
        query, external_calls=effective_external_calls
    )
    typer.echo(json.dumps({"urls": urls}, indent=2))


@app.command("build-dataset")
def build_dataset(run_dir: Path):
    package = read_package(run_dir / "package.json")
    package.write_dataset(run_dir.parent)
    typer.echo(str(run_dir))


@app.command("validate-package")
def validate_package(path: Path):
    package = read_package(path)
    report = package.validate_package()
    typer.echo(report.model_dump_json(indent=2))
    raise typer.Exit(0 if report.is_valid else 1)


@app.command("export-rag")
def export_rag(run_dir: Path):
    out = export_jsonl(run_dir)
    typer.echo(str(out))


@app.command()
def publish(run_dir: Path, profile: Path = DESTINATION_PROFILE_OPT):
    package = read_package(run_dir / "package.json")
    p = load_profile(profile)
    if p.destination.provider == "local_export":
        result = LocalExportDestination(run_dir.parent).publish(package)
    else:
        result = GenericRestDestination(p.destination).publish(package)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@doctor_app.callback(invoke_without_command=True)
def doctor_summary(ctx: typer.Context, profile: Path = DEFAULT_PROFILE_OPT):
    if ctx.invoked_subcommand is not None:
        return
    p = load_profile(profile)
    info = {
        "python": sys.version.split()[0],
        "profile": p.profile_name,
        "ai_provider": p.ai.provider,
        "destination": p.destination.provider,
        "dry_run": p.pipeline.dry_run,
    }
    typer.echo(json.dumps(info, indent=2))


@doctor_app.command("providers")
def doctor_providers(
    profile: Path = DEFAULT_PROFILE_OPT,
    offline: bool = typer.Option(
        False, "--offline", help="Run local payload/schema checks only; this overrides --live."
    ),
    live: bool = typer.Option(
        False, "--live", help="Run optional live smoke when env opt-in and credentials exist."
    ),
):
    p = load_profile(profile)
    result = run_provider_doctor(p, live=live and not offline)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


app.add_typer(doctor_app, name="doctor")


@app.command()
def version():
    typer.echo(__version__)
