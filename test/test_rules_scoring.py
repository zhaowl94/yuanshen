from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from yuanshen_score.constants import AttributeId
from yuanshen_score.models import Artifact
from yuanshen_score.rules import (
    RuleSetDocument,
    load_rule_set,
    rules_to_legacy,
)
from yuanshen_score.scoring import build_score_report, score_artifact


def test_bundled_rule_set_has_complete_legacy_data(rule_set: object) -> None:
    loaded = load_rule_set("legacy-v1")
    assert len(loaded.attribute_weights) == 10
    assert len(loaded.role_weights) == 68
    assert loaded.upgrade_steps[AttributeId.CRIT_RATE] == (
        Decimal("2.7"),
        Decimal("3.11"),
        Decimal("3.5"),
        Decimal("3.89"),
    )


def test_score_matches_historical_formula_without_mutation(
    artifact: Artifact,
) -> None:
    rules = load_rule_set()
    before_roles = {role: dict(weights) for role, weights in rules.role_weights.items()}
    assert score_artifact(artifact, "夜兰", rules) == Decimal("17.425994")
    assert rules.role_weights == before_roles


def test_score_unknown_role_is_actionable(artifact: Artifact) -> None:
    with pytest.raises(ValueError, match=r"unknown role.*available"):
        score_artifact(artifact, "不存在", load_rule_set())


def test_score_report_is_deterministic(artifact: Artifact) -> None:
    rules = load_rule_set()
    first = build_score_report(artifact, ["夜兰", "胡桃"], rules)
    second = build_score_report(artifact, ["夜兰", "胡桃"], rules)
    assert first == second
    assert first.metadata.input_sha256 == second.metadata.input_sha256


def test_legacy_rule_directory_and_export_are_independent(tmp_path: Path) -> None:
    source = Path("calc_item_score")
    for name in ("attrs_weight.json", "attrs_step.json", "attrs_choice.json", "roles_weight.json"):
        shutil.copy2(source / name, tmp_path / name)
    loaded = load_rule_set(tmp_path)
    exported = rules_to_legacy(loaded)
    exported["attrs_choice"]["暴击"] = 0
    assert loaded.selection_weights[AttributeId.CRIT_RATE] == 75


def test_custom_rule_document_round_trip(tmp_path: Path) -> None:
    base = load_rule_set()
    raw = {
        "schema_version": "1.0",
        "id": "custom",
        "attribute_weights": {
            key.value: str(value) for key, value in base.attribute_weights.items()
        },
        "upgrade_steps": {
            key.value: [str(value) for value in values]
            for key, values in base.upgrade_steps.items()
        },
        "selection_weights": {key.value: value for key, value in base.selection_weights.items()},
        "role_weights": {
            role: {key.value: str(value) for key, value in weights.items()}
            for role, weights in base.role_weights.items()
        },
    }
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    loaded = load_rule_set(path)
    assert loaded.id == "custom"
    assert loaded.attribute_weights == base.attribute_weights


@pytest.mark.parametrize(
    "change",
    [
        ("missing_attribute",),
        ("negative_step",),
        ("zero_selection",),
        ("missing_role_stat",),
        ("negative_role_weight",),
        ("empty_roles",),
    ],
)
def test_rule_document_validation_rejects_invalid(change: tuple[str], rule_set: object) -> None:
    base = load_rule_set()
    raw = {
        "id": "invalid",
        "attribute_weights": dict(base.attribute_weights),
        "upgrade_steps": dict(base.upgrade_steps),
        "selection_weights": dict(base.selection_weights),
        "role_weights": {role: dict(weights) for role, weights in base.role_weights.items()},
    }
    kind = change[0]
    if kind == "missing_attribute":
        raw["attribute_weights"].pop(AttributeId.FLAT_HP)
    elif kind == "negative_step":
        raw["upgrade_steps"][AttributeId.FLAT_HP] = (Decimal("-1"),)
    elif kind == "zero_selection":
        raw["selection_weights"][AttributeId.FLAT_HP] = 0
    elif kind == "missing_role_stat":
        next(iter(raw["role_weights"].values())).pop(next(iter(base.role_weights["夜兰"])))
    elif kind == "negative_role_weight":
        next(iter(raw["role_weights"].values()))[next(iter(base.role_weights["夜兰"]))] = -1
    else:
        raw["role_weights"] = {}
    with pytest.raises(ValidationError):
        RuleSetDocument.model_validate(raw)


def test_rule_loading_errors_are_clear(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_rule_set(tmp_path / "missing")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot load"):
        load_rule_set(bad)
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for name in ("attrs_weight.json", "attrs_step.json", "attrs_choice.json", "roles_weight.json"):
        (legacy / name).write_text("{}", encoding="utf-8")
    with pytest.raises((ValueError, ValidationError)):
        load_rule_set(legacy)
