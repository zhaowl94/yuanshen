"""TOML configuration without environment-variable side effects."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from yuanshen_score.models import StrictModel


class PathConfig(StrictModel):
    """Local writable paths."""

    model_dir: Path = Path(".yuanshen-score/models")
    output_dir: Path = Path("output")
    rules: Path | None = None


class OcrConfig(StrictModel):
    """OCR defaults."""

    device: Literal["cpu", "cuda"] = "cpu"
    confidence: float = Field(default=0.65, ge=0, le=1)
    languages: tuple[str, ...] = ("ch_sim", "en")

    @field_validator("languages")
    @classmethod
    def languages_not_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not language for language in value):
            raise ValueError("at least one non-empty OCR language is required")
        return value


class SimulationConfig(StrictModel):
    """Simulation defaults."""

    runs: int = Field(default=10_000, ge=1, le=1_000_000)
    target_level: int = Field(default=20, ge=0, le=20)


class AppConfig(StrictModel):
    """Root application configuration."""

    paths: PathConfig = PathConfig()
    ocr: OcrConfig = OcrConfig()
    simulation: SimulationConfig = SimulationConfig()


def _resolve_paths(config: AppConfig, base: Path) -> AppConfig:
    def resolve(path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else (base / path).resolve()

    return config.model_copy(
        update={
            "paths": config.paths.model_copy(
                update={
                    "model_dir": resolve(config.paths.model_dir),
                    "output_dir": resolve(config.paths.output_dir),
                    "rules": resolve(config.paths.rules),
                }
            )
        }
    )


def load_config(path: Path | None = None, *, cwd: Path | None = None) -> AppConfig:
    """Load explicit TOML or ``config.local.toml`` without reading environment variables."""

    working_directory = (cwd or Path.cwd()).resolve()
    selected = path.resolve() if path is not None else working_directory / "config.local.toml"
    if not selected.exists():
        if path is not None:
            raise ValueError(f"config file does not exist: {selected}")
        return _resolve_paths(AppConfig(), working_directory)
    try:
        with selected.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot load config file {selected}: {exc}") from exc
    return _resolve_paths(AppConfig.model_validate(raw), selected.parent)
