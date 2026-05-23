# Python 3.11–3.14 support policy

IngestForge public alpha `0.4.0a6` supports CPython **3.11, 3.12, 3.13, and 3.14**.

The project metadata uses:

```toml
requires-python = ">=3.11,<3.15"
```

The GitHub Actions CI matrix tests all supported versions on:

- `ubuntu-latest`
- `windows-latest`
- `macos-latest`

Required local checks before release:

```bash
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src tests
python -m pytest -q
python -m build
python -m twine check dist/*
python -m pip install --force-reinstall dist/*.whl
ingestforge --help
ingestforge version
```

Notes:

- Python 3.14 is a stable Python line, so it is included in the public support matrix.
- Optional providers may depend on their own SDK compatibility. Core CI avoids paid network calls and uses mock/local providers.
