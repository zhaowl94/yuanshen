from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from yuanshen_score.constants import AttributeId, PositionId
from yuanshen_score.models import Artifact, AttributeValue, OcrToken, ScoreRequest
from yuanshen_score.serialization import json_ready


def test_artifact_accepts_valid_percentage_points(artifact: Artifact) -> None:
    assert artifact.substats[AttributeId.CRIT_RATE] == Decimal("3.9")
    assert artifact.rarity == 5
    assert artifact.model_dump()["position"] is PositionId.SANDS


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"rarity": 4}, "Input should be 5"),
        ({"level": 21}, "less than or equal to 20"),
        ({"main_attribute": "mystery"}, "unknown main attribute"),
        (
            {"substats": {AttributeId.CRIT_RATE: Decimal("3.9")}},
            "three or four",
        ),
        (
            {
                "substats": {
                    AttributeId.FLAT_DEF: Decimal("0"),
                    AttributeId.ENERGY_RECHARGE: Decimal("5.2"),
                    AttributeId.CRIT_RATE: Decimal("3.9"),
                }
            },
            "positive",
        ),
        (
            {
                "main_attribute": "crit_rate",
                "substats": {
                    AttributeId.CRIT_RATE: Decimal("3.9"),
                    AttributeId.CRIT_DAMAGE: Decimal("6.2"),
                    AttributeId.FLAT_DEF: Decimal("16"),
                },
            },
            "main attribute",
        ),
        (
            {
                "level": 4,
                "substats": {
                    AttributeId.ENERGY_RECHARGE: Decimal("5.2"),
                    AttributeId.CRIT_RATE: Decimal("3.9"),
                    AttributeId.CRIT_DAMAGE: Decimal("6.2"),
                },
            },
            "level 4 or above",
        ),
    ],
)
def test_artifact_rejects_invalid_state(
    artifact: Artifact, changes: dict[str, object], message: str
) -> None:
    raw = artifact.model_dump()
    raw.update(changes)
    with pytest.raises(ValidationError, match=message):
        Artifact.model_validate(raw)


def test_strict_models_reject_unknown_fields(artifact: Artifact) -> None:
    raw = artifact.model_dump()
    raw["typo"] = 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        Artifact.model_validate(raw)


def test_score_request_validates_roles_and_target(artifact: Artifact) -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        ScoreRequest(artifact=artifact, roles=["夜兰", "夜兰"])
    with pytest.raises(ValidationError, match="must not be empty"):
        ScoreRequest(artifact=artifact, roles=[""])
    with pytest.raises(ValidationError, match="lower"):
        ScoreRequest(artifact=artifact, roles=["夜兰"], target_level=5)


def test_attribute_value_exposes_stable_id_label_and_unit() -> None:
    value = AttributeValue.from_pair(AttributeId.CRIT_RATE, Decimal("3.9"))
    assert json_ready(value) == {
        "display_name_zh": "暴击",
        "id": "crit_rate",
        "unit": "percentage_point",
        "value": 3.9,
    }


def test_ocr_token_validates_confidence() -> None:
    with pytest.raises(ValidationError):
        OcrToken(text="攻击力", confidence=1.1)
    with pytest.raises(ValidationError):
        OcrToken(text="", confidence=0.5)
