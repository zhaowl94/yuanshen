"""Conversions for the historical Chinese dictionary format."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from yuanshen_score.constants import (
    ATTRIBUTE_LABELS_ZH,
    LEGACY_ATTRIBUTE_IDS,
    LEGACY_MAIN_ATTRIBUTE_IDS,
    LEGACY_POSITION_IDS,
    MAIN_ATTRIBUTE_LEGACY,
    POSITION_NUMBER,
    AttributeId,
    PositionId,
)
from yuanshen_score.models import Artifact, ScoreRequest


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric, not boolean")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc


def _position(value: Any) -> PositionId:
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            return LEGACY_POSITION_IDS[value]
        except KeyError as exc:
            raise ValueError(f"legacy position must be between 1 and 5: {value!r}") from exc
    try:
        return PositionId(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown artifact position: {value!r}") from exc


def legacy_item_to_artifact(raw: Mapping[str, Any]) -> Artifact:
    """Convert the historical ``item`` mapping to the canonical model."""

    try:
        raw_position = raw["position"]
        raw_main = str(raw["major_attr"])
        raw_level = raw["level"]
        raw_substats = raw["minor_attr"]
    except KeyError as exc:
        raise ValueError(f"legacy item is missing required field: {exc.args[0]}") from exc

    if not isinstance(raw_substats, Mapping):
        raise ValueError("legacy item minor_attr must be an object")
    try:
        main_attribute = LEGACY_MAIN_ATTRIBUTE_IDS.get(raw_main, raw_main)
        substats = {
            LEGACY_ATTRIBUTE_IDS[str(label)]: amount
            for label, value in raw_substats.items()
            if (amount := _decimal(value, f"minor_attr.{label}")) > 0
        }
    except KeyError as exc:
        raise ValueError(f"unknown legacy substat label: {exc.args[0]!r}") from exc

    return Artifact(
        position=_position(raw_position),
        main_attribute=main_attribute,
        level=int(raw_level),
        rarity=raw.get("rarity", 5),
        substats=substats,
        name=raw.get("name"),
        set_name=raw.get("set_name"),
    )


def artifact_to_legacy(artifact: Artifact) -> dict[str, Any]:
    """Convert a canonical artifact to a fresh historical mapping."""

    values = {label: 0.0 for label in LEGACY_ATTRIBUTE_IDS}
    for identifier, value in artifact.substats.items():
        values[ATTRIBUTE_LABELS_ZH[identifier]] = float(value)
    return {
        "position": POSITION_NUMBER[artifact.position],
        "major_attr": MAIN_ATTRIBUTE_LEGACY.get(artifact.main_attribute, artifact.main_attribute),
        "level": artifact.level,
        "minor_attr": values,
    }


def legacy_request_to_score_request(raw: Mapping[str, Any]) -> ScoreRequest:
    """Convert a historical top-level input object containing ``item``."""

    if "item" not in raw:
        raise ValueError("legacy input requires OCR because it does not contain an item object")
    roles = raw.get("roles")
    if not isinstance(roles, list):
        raise ValueError("legacy input roles must be a list")
    request: dict[str, Any] = {
        "artifact": legacy_item_to_artifact(raw["item"]),
        "roles": roles,
    }
    for field in ("ruleset", "runs", "target_level", "seed"):
        if field in raw:
            request[field] = raw[field]
    return ScoreRequest.model_validate(request)


def legacy_attribute_mapping(
    raw: Mapping[str, Any],
) -> dict[AttributeId, Decimal]:
    """Convert one historical attribute mapping for compatibility helpers."""

    try:
        return {
            LEGACY_ATTRIBUTE_IDS[str(label)]: _decimal(value, str(label))
            for label, value in raw.items()
        }
    except KeyError as exc:
        raise ValueError(f"unknown legacy attribute label: {exc.args[0]!r}") from exc
