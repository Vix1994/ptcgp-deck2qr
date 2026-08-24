# Contributing

Thanks for helping build `ptcgp-deck2qr`.

## Before opening a change

- Confirm that the change belongs to the current screenshot-to-Deck-Text milestone.
- Check `prd.md` and the relevant documents under `docs/`.
- Open or update an ADR when introducing a model, a service, a new authoritative data source, a file-format break, or a cross-module dependency.

## Local setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

See `docs/development.md` for PowerShell and POSIX commands.

## Pull request requirements

A change is ready for review when:

- The scope is explained in plain language.
- Tests cover new behavior and failure behavior.
- The full local quality gate passes.
- User screenshots or card assets are not added without provenance and redistribution permission.
- Public behavior and format changes update the relevant documentation.
- `CHANGELOG.md` is updated for user-visible changes.

By submitting a contribution, you agree to license it under the project's
[MIT License](LICENSE) and confirm that you have the right to do so.

## Commit guidance

Keep commits focused. Suggested prefixes are:

```text
feat:      user-visible capability
fix:       user-visible defect
docs:      documentation only
test:      tests only
refactor:  behavior-preserving code change
chore:     tooling or maintenance
```

## Review priorities

Reviewers should prioritize, in order:

1. Incorrect accepted decks.
2. Loss of determinism or format compatibility.
3. Database identity mistakes.
4. Missing diagnostics for rejected inputs.
5. Performance and maintainability.
