from ingestforge import pipeline

pipe = pipeline("profiles/manual_safe.yaml")
package = pipe.ingest_url(
    "https://example.com/article",
    dry_run=True,
    external_calls="disabled",
    write_dataset=True,
)
print(package.job_id)
