from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from yuanshen_score.config import AppConfig, OcrConfig, load_config


def test_default_config_is_resolved_without_creating_files(tmp_path: Path) -> None:
    config = load_config(cwd=tmp_path)
    assert config.paths.model_dir == tmp_path / ".yuanshen-score/models"
    assert config.paths.output_dir == tmp_path / "output"
    assert not (tmp_path / "config.local.toml").exists()


def test_explicit_config_resolves_paths_relative_to_file(tmp_path: Path) -> None:
    nested = tmp_path / "settings"
    nested.mkdir()
    path = nested / "local.toml"
    path.write_text(
        """
[paths]
model_dir = "models"
output_dir = "results"
rules = "rules.json"
[ocr]
device = "cuda"
confidence = 0.8
languages = ["ch_sim"]
[simulation]
runs = 123
target_level = 16
""".strip(),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.paths.model_dir == nested / "models"
    assert config.paths.rules == nested / "rules.json"
    assert config.ocr.device == "cuda"
    assert config.simulation.target_level == 16


def test_config_errors_are_actionable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_config(tmp_path / "missing.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot load"):
        load_config(bad)
    with pytest.raises(ValidationError):
        OcrConfig(languages=())
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"unknown": 1})
