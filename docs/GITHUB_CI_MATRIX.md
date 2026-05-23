# GitHub CI matrix

The CI workflow is intentionally strict for a public library:

```yaml
os: [ubuntu-latest, windows-latest, macos-latest]
python-version: ["3.11", "3.12", "3.13", "3.14"]
```

Every matrix job runs:

1. editable install with dev extras;
2. `ruff check`;
3. `ruff format --check`;
4. `compileall`;
5. `pytest`;
6. CLI smoke checks.

A separate package job builds wheel/sdist, runs `twine check`, installs the built wheel, and runs release hygiene checks.
