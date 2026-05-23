from ingestforge import ingest_url

package = ingest_url("https://example.com/article", write_dataset=True)
print(package.job_id)
print(package.package_hash)
