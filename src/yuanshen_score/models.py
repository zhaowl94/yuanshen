"""Validated public data models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from yuanshen_score.constants import (
    ATTRIBUTE_LABELS_ZH,
    ATTRIBUTE_UNITS,
    MAIN_ATTRIBUTE_LABELS_ZH,
    SCHEMA_VERSION,
    AttributeId,
    PositionId,
)

JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda value: float(value), return_type=float, when_used="json"),
]


class StrictModel(BaseModel):
    """Shared strict model settings."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Artifact(StrictModel):
    """A validated five-star artifact.

    Percentage values use percentage points: ``3.9`` means ``3.9%``.
    """

    position: PositionId
    main_attribute: str = Field(min_length=1)
    level: int = Field(ge=0, le=20)
    rarity: Literal[5] = 5
    substats: dict[AttributeId, JsonDecimal]
    name: str | None = None
    set_name: str | None = None

    @field_validator("main_attribute")
    @classmethod
    def validate_main_attribute(cls, value: str) -> str:
        if value not in MAIN_ATTRIBUTE_LABELS_ZH:
            valid = ", ".join(sorted(MAIN_ATTRIBUTE_LABELS_ZH))
            raise ValueError(f"unknown main attribute {value!r}; expected one of: {valid}")
        return value

    @field_validator("substats")
    @classmethod
    def validate_substats(cls, value: dict[AttributeId, Decimal]) -> dict[AttributeId, Decimal]:
        if not 3 <= len(value) <= 4:
            raise ValueError("a five-star artifact must contain three or four positive substats")
        invalid = {key.value: amount for key, amount in value.items() if amount <= 0}
        if invalid:
            raise ValueError(f"substat values must be positive: {invalid}")
        return value

    @model_validator(mode="after")
    def validate_main_substat_conflict(self) -> Artifact:
        try:
            main_substat = AttributeId(self.main_attribute)
        except ValueError:
            main_substat = None
        if main_substat is not None and main_substat in self.substats:
            raise ValueError("main attribute cannot also appear as a substat")
        if self.level >= 4 and len(self.substats) == 3:
            raise ValueError("a five-star artifact at level 4 or above must have four substats")
        return self


class AttributeValue(StrictModel):
    """A localized attribute value for machine and human output."""

    id: AttributeId
    display_name_zh: str
    value: JsonDecimal
    unit: Literal["flat", "percentage_point"]

    @classmethod
    def from_pair(cls, identifier: AttributeId, value: Decimal) -> AttributeValue:
        return cls(
            id=identifier,
            display_name_zh=ATTRIBUTE_LABELS_ZH[identifier],
            value=value,
            unit=ATTRIBUTE_UNITS[identifier],  # type: ignore[arg-type]
        )


class ScoreRequest(StrictModel):
    """Canonical request for scoring or simulation."""

    schema_version: Literal["2.0"] = SCHEMA_VERSION
    artifact: Artifact
    roles: list[str] = Field(min_length=1)
    ruleset: str = "legacy-v1"
    runs: int | None = Field(default=None, ge=1, le=1_000_000)
    target_level: int | None = Field(default=None, ge=0, le=20)
    seed: int | None = Field(default=None, ge=0, le=18_446_744_073_709_551_615)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("roles must not contain duplicates")
        if any(not role for role in value):
            raise ValueError("role names must not be empty")
        return value

    @model_validator(mode="after")
    def validate_target(self) -> ScoreRequest:
        if self.target_level is not None and self.target_level < self.artifact.level:
            raise ValueError("target_level must not be lower than the artifact level")
        return self


class RoleScore(StrictModel):
    """Current score for one role."""

    role: str
    score: JsonDecimal


class ScoreMetadata(StrictModel):
    """Metadata shared by deterministic score reports."""

    schema_version: Literal["2.0"] = SCHEMA_VERSION
    application_version: str
    ruleset: str
    input_sha256: str


class ScoreReport(StrictModel):
    """Machine-readable score output."""

    metadata: ScoreMetadata
    artifact: Artifact
    substat_details: list[AttributeValue]
    scores: list[RoleScore]


class DistributionSummary(StrictModel):
    """Stable statistical summary for a simulation distribution."""

    count: int = Field(ge=1)
    minimum: JsonDecimal
    q1: JsonDecimal
    median: JsonDecimal
    mean: JsonDecimal
    q3: JsonDecimal
    maximum: JsonDecimal


class RoleSimulation(StrictModel):
    """Simulation result for one role."""

    role: str
    current_score: JsonDecimal
    final_score: DistributionSummary
    score_gain: DistributionSummary
    raw_final_scores: list[JsonDecimal] | None = None


class SimulationMetadata(ScoreMetadata):
    """Reproducibility metadata for simulation reports."""

    generated_at: datetime
    seed: int
    rng_algorithm: str
    runs: int
    target_level: int


class SimulationReport(StrictModel):
    """Machine-readable Monte Carlo report."""

    metadata: SimulationMetadata
    artifact: Artifact
    substat_details: list[AttributeValue]
    results: list[RoleSimulation]


class OcrToken(StrictModel):
    """Engine-neutral OCR token."""

    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    bounding_box: (
        tuple[
            tuple[float, float],
            tuple[float, float],
            tuple[float, float],
            tuple[float, float],
        ]
        | None
    ) = None


class OcrParseResult(StrictModel):
    """Parsed artifact and privacy-minimized OCR metadata."""

    schema_version: Literal["2.0"] = SCHEMA_VERSION
    artifact: Artifact
    relevant_tokens: list[OcrToken]
    warnings: list[str] = Field(default_factory=list)
