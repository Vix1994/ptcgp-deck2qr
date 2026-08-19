# Development guide

## Prerequisites

- Python 3.11 or newer.
- Git.
- An external `ptcgp-database/dist` directory for future integration tests.

The project does not require Node.js, a GPU, Tesseract, PyTorch, or a web service in the current milestone.

## CLI smoke test

The recognition milestone exposes two commands. The database path is required
unless `PTCGP_DATABASE_PATH` is set; no machine-specific path is compiled into
the package.

```powershell
ptcgp-deck2qr build-index --database-path <database-dist> --output data\index\fingerprint.json
ptcgp-deck2qr recognize <screenshot> --energy lightning --database-path <database-dist> --output-dir output
```

`recognize` always attempts to write `recognition.json` and `recognized.png`.
It writes `deck.txt` only when all card entities and counts are accepted and
the aggregate validates as a 20-card deck. A rejected aggregate may have a
`deck.partial.txt` for inspection.

## Setup on Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Activate the environment if desired:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Setup on POSIX shells

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

## Quality gate

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest
```

Apply automated formatting and safe lint fixes with:

```bash
python -m ruff format .
python -m ruff check --fix .
```

## Coding standards

- Use type annotations on public and module-boundary functions.
- Use frozen dataclasses for immutable domain values where practical.
- Keep I/O at the edges; parsing and scoring logic should accept values and return values.
- Use `pathlib.Path` instead of string path concatenation.
- Use explicit exceptions with actionable context at module boundaries.
- Do not catch broad exceptions unless adding context and re-raising or converting to a domain error.
- Avoid global mutable registries and implicit network requests.
- Store normalized scores with their metric names; do not collapse unrelated metrics into an unexplained confidence number.

## Adding dependencies

Before adding a runtime dependency:

1. Show which current requirement it satisfies.
2. Estimate installation and runtime cost.
3. Check its license and native-platform implications.
4. Prefer an existing dependency or standard-library solution when comparable.
5. Add an ADR for models, services, OCR engines, databases, or dependencies that materially change distribution size.

## Database development

Never commit the external database into this repository. Future commands should accept a path or an environment-specific configuration at the CLI boundary.

Local examples may use:

```text
H:\CodexCode\ptcgp-database\dist
```

Tests must not assume that this machine-specific path exists.

## Documentation changes

- Product-scope changes update `prd.md`.
- Deck Text behavior changes update `docs/deck-text-format-v1.md` and require compatibility tests.
- Dependency or module-boundary changes update `docs/architecture.md` and may require an ADR.
- User-visible changes update `README.md` and `CHANGELOG.md`.
