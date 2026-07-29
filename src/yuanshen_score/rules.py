"""Versioned scoring and upgrade rule loading."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from yuanshen_score.constants import (
    ATTRIBUTE_LABELS_ZH,
    ATTRIBUTE_ROLE_STAT,
    LEGACY_ATTRIBUTE_IDS,
    LEGACY_ROLE_STAT_IDS,
    ROLE_STAT_LABELS_ZH,
    RULE_SCHEMA_VERSION,
    AttributeId,
    RoleStatId,
)
from yuanshen_score.models import JsonDecimal, StrictModel


class RuleSetDocument(StrictModel):
    """Portable, versioned custom rule document."""

    schema_version: Literal["1.0"] = RULE_SCHEMA_VERSION
    id: str = Field(min_length=1)
    attribute_weights: dict[AttributeId, JsonDecimal]
    upgrade_steps: dict[AttributeId, tuple[JsonDecimal, ...]]
    selection_weights: dict[AttributeId, int]
    role_weights: dict[str, dict[RoleStatId, JsonDecimal]]

    @field_validator("attribute_weights", "upgrade_steps", "selection_weights")
    @classmethod
    def require_all_attributes(cls, value: Mapping[AttributeId, Any]) -> Mapping[AttributeId, Any]:
        missing = set(AttributeId) - set(value)
        extra = set(value) - set(AttributeId)
        if missing or extra:
            raise ValueError(
                "attribute keys must exactly match the supported set; "
                f"missing={sorted(item.value for item in missing)}, "
                f"extra={sorted(str(item) for item in extra)}"
            )
        return value

    @field_validator("upgrade_steps")
    @classmethod
    def validate_steps(
        cls, value: dict[AttributeId, tuple[Decimal, ...]]
    ) -> dict[AttributeId, tuple[Decimal, ...]]:
        for identifier, steps in value.items():
            if not steps or any(step <= 0 for step in steps):
                raise ValueError(f"upgrade steps for {identifier.value} must be positive")
        return value

    @field_validator("selection_weights")
    @classmethod
    def validate_selection(cls, value: dict[AttributeId, int]) -> dict[AttributeId, int]:
        if any(weight <= 0 for weight in value.values()):
            raise ValueError("selection weights must be positive")
        return value

    @field_validator("role_weights")
    @classmethod
    def validate_roles(
        cls, value: dict[str, dict[RoleStatId, Decimal]]
    ) -> dict[str, dict[RoleStatId, Decimal]]:
        required = set(RoleStatId)
        if not value:
            raise ValueError("at least one role is required")
        for role, weights in value.items():
            if not role:
                raise ValueError("role names must not be empty")
            if set(weights) != required:
                raise ValueError(f"role {role!r} must define every role weight")
            if any(weight < 0 for weight in weights.values()):
                raise ValueError(f"role {role!r} contains a negative weight")
        return value


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Validated immutable-by-convention runtime rule set."""

    id: str
    attribute_weights: Mapping[AttributeId, Decimal]
    upgrade_steps: Mapping[AttributeId, tuple[Decimal, ...]]
    selection_weights: Mapping[AttributeId, int]
    role_weights: Mapping[str, Mapping[RoleStatId, Decimal]]

    def role_weight_for(self, role: str, attribute: AttributeId) -> Decimal:
        try:
            weights = self.role_weights[role]
        except KeyError as exc:
            available = ", ".join(sorted(self.role_weights))
            raise ValueError(f"unknown role {role!r}; available roles: {available}") from exc
        return weights[ATTRIBUTE_ROLE_STAT[attribute]]


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal, parse_int=Decimal)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load rule file {path}: {exc}") from exc


def _legacy_document(directory: Path, identifier: str) -> RuleSetDocument:
    attrs_weight = _read_json(directory / "attrs_weight.json")
    attrs_step = _read_json(directory / "attrs_step.json")
    attrs_choice = _read_json(directory / "attrs_choice.json")
    roles_weight = _read_json(directory / "roles_weight.json")

    def map_attributes(raw: Mapping[str, Any]) -> dict[AttributeId, Any]:
        try:
            return {LEGACY_ATTRIBUTE_IDS[key]: value for key, value in raw.items()}
        except KeyError as exc:
            raise ValueError(f"unknown legacy attribute label: {exc.args[0]!r}") from exc

    try:
        mapped_roles = {
            role: {LEGACY_ROLE_STAT_IDS[key]: value for key, value in weights.items()}
            for role, weights in roles_weight.items()
        }
    except KeyError as exc:
        raise ValueError(f"unknown legacy role-weight label: {exc.args[0]!r}") from exc

    return RuleSetDocument(
        id=identifier,
        attribute_weights=map_attributes(attrs_weight),
        upgrade_steps=map_attributes(attrs_step),
        selection_weights=map_attributes(attrs_choice),
        role_weights=mapped_roles,
    )


def _bundled_directory() -> Path:
    resource = files("yuanshen_score.data").joinpath("legacy-v1")
    return Path(str(resource))


def load_rule_set(source: str | Path | None = None) -> RuleSet:
    """Load the bundled legacy rules, a legacy directory, or a v1 JSON document."""

    if source is None or str(source) == "legacy-v1":
        document = _legacy_document(_bundled_directory(), "legacy-v1")
    else:
        path = Path(source).expanduser().resolve()
        if path.is_dir():
            document = _legacy_document(path, path.name)
        elif path.is_file():
            raw = _read_json(path)
            document = RuleSetDocument.model_validate(raw)
        else:
            raise ValueError(f"rule source does not exist: {path}")

    return RuleSet(
        id=document.id,
        attribute_weights=dict(document.attribute_weights),
        upgrade_steps={key: tuple(value) for key, value in document.upgrade_steps.items()},
        selection_weights=dict(document.selection_weights),
        role_weights={role: dict(weights) for role, weights in document.role_weights.items()},
    )


def rules_to_legacy(rule_set: RuleSet) -> dict[str, dict[str, Any]]:
    """Return independent legacy dictionaries for compatibility wrappers."""

    return {
        "attrs_weight": {
            ATTRIBUTE_LABELS_ZH[key]: float(value)
            for key, value in rule_set.attribute_weights.items()
        },
        "attrs_step": {
            ATTRIBUTE_LABELS_ZH[key]: [float(step) for step in steps]
            for key, steps in rule_set.upgrade_steps.items()
        },
        "attrs_choice": {
            ATTRIBUTE_LABELS_ZH[key]: value for key, value in rule_set.selection_weights.items()
        },
        "roles_weight": {
            role: {ROLE_STAT_LABELS_ZH[key]: float(value) for key, value in weights.items()}
            for role, weights in rule_set.role_weights.items()
        },
    }
