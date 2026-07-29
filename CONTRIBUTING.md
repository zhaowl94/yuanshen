# Contributing

## Setup

```powershell
uv sync --extra dev --extra plot
```

Use Python 3.11 or 3.12. Do not add real game screenshots, OCR models, account identifiers,
`config.local.toml`, or `input_param.json` to Git.

## Required checks

```powershell
uv run ruff check src calc_item_score test
uv run ruff format --check src calc_item_score test
uv run mypy src
uv run pytest -m "not real_ocr" --cov=yuanshen_score --cov-branch --cov-report=term-missing
uv run pip-audit --local --skip-editable --progress-spinner off
uv build
```

Changes to scoring, upgrade sampling, schema conversion, or old wrappers require focused
regression tests. Core scoring and simulation branches must remain fully covered; overall branch
coverage must remain at or above 90%.

OCR changes also require the explicit model install/verify flow and `pytest -m real_ocr`. The CI
merge gate runs this CPU inference test with synthetic text; do not add private screenshots.

## Compatibility

- Do not remove the historical entry point or Chinese input keys in a 1.x release.
- Add new machine fields through a versioned schema.
- Never change the default `legacy-v1` rule data in place.
- Document deliberate behavior changes in `CHANGELOG.md` and `docs/MIGRATION.md`.
