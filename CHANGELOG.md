# Changelog

All notable changes follow Keep a Changelog conventions. The project uses Semantic Versioning
for its public CLI, schemas, and Python compatibility API.

## [1.0.0] - 2026-07-29

### Added

- `yuanshen_score` package and `yuanshen-score` CLI.
- Strict v2 JSON schemas with stable English identifiers and Chinese display names.
- Reproducible Monte Carlo simulation with recorded seeds and versioned RNG semantics.
- Current-score, final-score, and score-gain summaries.
- Resumable batch processing with atomic state files and failure isolation.
- Resume integrity checks covering source, execution options, and result-file hashes.
- Optional plotting and EasyOCR dependency groups.
- Explicit OCR model installation, local checksums, confidence gating, and privacy-minimized output.
- Windows/Ubuntu CI for Python 3.11 and 3.12.
- Comprehensive unit, property, contract, integration, CLI, packaging, and real OCR tests.

### Changed

- Frozen historical weights as the explicit `legacy-v1` rule set.
- Replaced the monolithic notebook-export script with a compatibility wrapper.
- Moved mutable input and real screenshots out of version control.

### Fixed

- Custom loader paths now work.
- Role and substat-choice dictionaries are no longer polluted by previous calls.
- OCR parsing no longer relies on unchecked fixed indexes.
- Known historical OCR confusions are corrected with explicit audit warnings; suspicious
  substat-like text fails closed.
- Simulation runs can be reproduced from their recorded seed.
- Invalid roles, levels, fields, units, and substat combinations fail with actionable errors.
- CLI, input-file, local-config, and built-in defaults now follow the documented precedence.
- Installed legacy loaders fall back to the wheel's bundled `legacy-v1` data.

### Compatibility

- Historical Chinese JSON, command path, and module-level functions remain supported throughout
  the 1.x series.
- Known incorrect behavior is documented but intentionally not reproduced.

[1.0.0]: https://github.com/zhaowl94/yuanshen/releases/tag/v1.0.0
