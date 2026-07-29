"""Historical function wrappers retained for the complete 1.x series."""

from __future__ import annotations

import copy
import json
import random
import warnings
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from yuanshen_score.config import load_config
from yuanshen_score.constants import (
    LEGACY_ATTRIBUTE_IDS,
    LEGACY_ROLE_STAT_IDS,
    AttributeId,
)
from yuanshen_score.legacy import artifact_to_legacy, legacy_item_to_artifact
from yuanshen_score.ocr import EasyOcrEngine
from yuanshen_score.parser import parse_legacy_texts
from yuanshen_score.plotting import create_figure
from yuanshen_score.rules import RuleSet, load_rule_set, rules_to_legacy
from yuanshen_score.scoring import score_artifact
from yuanshen_score.simulation import StableRandom, simulate, upgrade_to_level
from yuanshen_score.simulation import upgrade_once as core_upgrade_once

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_DIR = _SOURCE_ROOT / "calc_item_score"
_WARNED = False


def _warn() -> None:
    global _WARNED
    if not _WARNED:
        warnings.warn(
            "calc_item_score.py 是 1.x 兼容入口；新代码请使用 yuanshen_score API 或 "
            "yuanshen-score CLI",
            FutureWarning,
            stacklevel=3,
        )
        _WARNED = True


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _default_path(name: str) -> Path:
    candidates = [Path.cwd() / name, _LEGACY_DIR / name]
    if name == "input_param.json":
        candidates.append(_LEGACY_DIR / "input_param.example.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"legacy data file not found: {name}")


def _load(name: str, input_path: str | Path | None) -> dict[str, Any]:
    _warn()
    try:
        path = Path(input_path) if input_path is not None else _default_path(name)
    except FileNotFoundError:
        bundled_name = name.removesuffix(".json")
        bundled = rules_to_legacy(load_rule_set())
        if bundled_name not in bundled:
            raise
        return bundled[bundled_name]
    value = _read_json(path.resolve())
    if not isinstance(value, dict):
        raise ValueError(f"legacy data file must contain an object: {path}")
    return cast(dict[str, Any], value)


def load_roles_weight(input_path: str | Path | None = None) -> dict[str, dict[str, float]]:
    return cast(dict[str, dict[str, float]], _load("roles_weight.json", input_path))


def load_attrs_step(input_path: str | Path | None = None) -> dict[str, list[float]]:
    return cast(dict[str, list[float]], _load("attrs_step.json", input_path))


def load_attrs_weight(input_path: str | Path | None = None) -> dict[str, float]:
    return cast(dict[str, float], _load("attrs_weight.json", input_path))


def load_input_param(input_path: str | Path | None = None) -> dict[str, Any]:
    return _load("input_param.json", input_path)


def load_attrs_choice(input_path: str | Path | None = None) -> dict[str, int]:
    return cast(dict[str, int], _load("attrs_choice.json", input_path))


def check_valid(item: Mapping[str, Any]) -> bool:
    _warn()
    try:
        legacy_item_to_artifact(item)
    except (TypeError, ValueError, KeyError):
        return False
    return True


def _attribute_map(raw: Mapping[str, Any]) -> dict[AttributeId, Decimal]:
    try:
        return {LEGACY_ATTRIBUTE_IDS[label]: Decimal(str(value)) for label, value in raw.items()}
    except KeyError as exc:
        raise ValueError(f"unknown legacy attribute: {exc.args[0]!r}") from exc


def _rule_set(
    *,
    attrs_weight: Mapping[str, Any] | None = None,
    roles_weight: Mapping[str, Mapping[str, Any]] | None = None,
    attrs_step: Mapping[str, list[Any]] | None = None,
    attrs_choice: Mapping[str, Any] | None = None,
) -> RuleSet:
    base = load_rule_set()
    attribute_weights = (
        _attribute_map(attrs_weight) if attrs_weight is not None else dict(base.attribute_weights)
    )
    upgrade_steps = (
        {
            identifier: tuple(values)
            for identifier, values in _attribute_map_lists(attrs_step).items()
        }
        if attrs_step is not None
        else dict(base.upgrade_steps)
    )
    selection_weights = (
        {LEGACY_ATTRIBUTE_IDS[label]: int(value) for label, value in attrs_choice.items()}
        if attrs_choice is not None
        else dict(base.selection_weights)
    )
    if roles_weight is None:
        runtime_roles = {name: dict(weights) for name, weights in base.role_weights.items()}
    else:
        runtime_roles = {}
        for role, weights in roles_weight.items():
            try:
                runtime_roles[role] = {
                    stable: Decimal(str(weights[label]))
                    for label, stable in LEGACY_ROLE_STAT_IDS.items()
                }
            except KeyError as exc:
                raise ValueError(f"role {role!r} is missing legacy weight {exc.args[0]!r}") from exc
    return RuleSet(
        id=base.id,
        attribute_weights=attribute_weights,
        upgrade_steps=upgrade_steps,
        selection_weights=selection_weights,
        role_weights=runtime_roles,
    )


def _attribute_map_lists(
    raw: Mapping[str, list[Any]],
) -> dict[AttributeId, tuple[Decimal, ...]]:
    try:
        return {
            LEGACY_ATTRIBUTE_IDS[label]: tuple(Decimal(str(value)) for value in values)
            for label, values in raw.items()
        }
    except KeyError as exc:
        raise ValueError(f"unknown legacy attribute: {exc.args[0]!r}") from exc


def _replace_item(target: dict[str, Any], artifact: Any) -> dict[str, Any]:
    converted = artifact_to_legacy(artifact)
    target.clear()
    target.update(converted)
    return target


def upgrade_once(
    item: dict[str, Any],
    attrs_step: Mapping[str, list[Any]] | None = None,
    attrs_choice: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _warn()
    rule_set = _rule_set(attrs_step=attrs_step, attrs_choice=attrs_choice)
    artifact = core_upgrade_once(
        legacy_item_to_artifact(item),
        rule_set,
        StableRandom(random.getrandbits(64)),
    )
    return _replace_item(item, artifact)


def upgrade(
    item: dict[str, Any],
    level: int = 20,
    attrs_step: Mapping[str, list[Any]] | None = None,
    attrs_choice: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _warn()
    rule_set = _rule_set(attrs_step=attrs_step, attrs_choice=attrs_choice)
    artifact = upgrade_to_level(
        legacy_item_to_artifact(item),
        level,
        rule_set,
        StableRandom(random.getrandbits(64)),
    )
    return _replace_item(item, artifact)


def trans_role_weight(role_weight: Mapping[str, Any]) -> dict[str, Any]:
    _warn()
    result = dict(role_weight)
    result.update(
        {
            "小生命": role_weight["生命"],
            "小攻击": role_weight["攻击"],
            "小防御": role_weight["防御"],
            "大生命": role_weight["生命"],
            "大攻击": role_weight["攻击"],
            "大防御": role_weight["防御"],
        }
    )
    return result


def calc_score(
    item: Mapping[str, Any],
    role: str,
    attrs_weight: Mapping[str, Any] | None = None,
    roles_weight: Mapping[str, Mapping[str, Any]] | None = None,
) -> float:
    _warn()
    rule_set = _rule_set(attrs_weight=attrs_weight, roles_weight=roles_weight)
    return float(score_artifact(legacy_item_to_artifact(item), role, rule_set))


def calc_score_roles(
    input_param: Mapping[str, Any] | None = None,
    roles_weight: Mapping[str, Mapping[str, Any]] | None = None,
    attrs_weight: Mapping[str, Any] | None = None,
    attrs_step: Mapping[str, list[Any]] | None = None,
    attrs_choice: Mapping[str, Any] | None = None,
) -> Any:
    _warn()
    params = copy.deepcopy(dict(input_param) if input_param is not None else load_input_param())
    if "item" not in params:
        params["item"] = parse_result(ocr_item(params))
    rule_set = _rule_set(
        attrs_weight=attrs_weight,
        roles_weight=roles_weight,
        attrs_step=attrs_step,
        attrs_choice=attrs_choice,
    )
    report = simulate(
        legacy_item_to_artifact(params["item"]),
        list(params["roles"]),
        rule_set,
        runs=int(params.get("runs", 10_000)),
        target_level=int(params.get("target_level", 20)),
        seed=params.get("seed"),
    )
    create_figure(report)
    import matplotlib.pyplot as pyplot

    return pyplot


def ocr_item(input_param: Mapping[str, Any] | None = None) -> list[str]:
    _warn()
    params = dict(input_param) if input_param is not None else load_input_param()
    config = load_config(cwd=_LEGACY_DIR)
    image = Path(params["item_path"])
    if not image.is_absolute():
        image = _LEGACY_DIR / image
    model_dir = Path(params.get("model_dir", config.paths.model_dir))
    engine = EasyOcrEngine(
        model_dir,
        device=str(params.get("device", config.ocr.device)),
        languages=config.ocr.languages,
    )
    result = [token.text for token in engine.read(image)]
    print(result)
    return result


def parse_result(result: list[str]) -> dict[str, Any]:
    _warn()
    item = artifact_to_legacy(parse_legacy_texts(result))
    print(item)
    return item


def legacy_main() -> int:
    """Run the historical interactive workflow."""

    params = load_input_param()
    pyplot = calc_score_roles(params)
    pyplot.show()
    return 0


def bundled_legacy_data() -> dict[str, dict[str, Any]]:
    """Expose fresh copies for migration tooling and tests."""

    return rules_to_legacy(load_rule_set())
