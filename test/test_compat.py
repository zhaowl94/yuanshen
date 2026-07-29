from __future__ import annotations

import copy
import json
import warnings
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import yuanshen_score.compat as compat
from yuanshen_score.constants import AttributeId
from yuanshen_score.legacy import (
    artifact_to_legacy,
    legacy_attribute_mapping,
    legacy_item_to_artifact,
    legacy_request_to_score_request,
)
from yuanshen_score.models import OcrToken


def test_legacy_loaders_support_default_and_custom_paths(tmp_path: Path) -> None:
    custom = tmp_path / "weights.json"
    custom.write_text('{"暴击":2}', encoding="utf-8")
    assert compat.load_attrs_weight(custom) == {"暴击": 2}
    assert "夜兰" in compat.load_roles_weight()
    assert "暴击" in compat.load_attrs_step()
    assert compat.load_attrs_choice()["暴击"] == 75
    assert "roles" in compat.load_input_param(Path("calc_item_score/input_param.example.json"))


def test_legacy_validation_score_and_role_transform(
    legacy_item: dict[str, object],
) -> None:
    assert compat.check_valid(legacy_item)
    invalid = copy.deepcopy(legacy_item)
    invalid["level"] = 21
    assert not compat.check_valid(invalid)
    roles = compat.load_roles_weight()
    original = dict(roles["夜兰"])
    expanded = compat.trans_role_weight(roles["夜兰"])
    assert expanded["小生命"] == original["生命"]
    assert roles["夜兰"] == original
    assert compat.calc_score(legacy_item, "夜兰") == pytest.approx(17.4259944)


def test_legacy_upgrade_mutates_item_but_not_choice(
    legacy_item: dict[str, object],
) -> None:
    item = copy.deepcopy(legacy_item)
    choices = compat.load_attrs_choice()
    before = dict(choices)
    assert compat.upgrade_once(item, attrs_choice=choices) is item
    assert item["level"] == 8
    assert choices == before
    item = copy.deepcopy(legacy_item)
    assert compat.upgrade(item, 12) is item
    assert item["level"] == 12


def test_legacy_parser_prints_and_returns_dict(capsys: pytest.CaptureFixture[str]) -> None:
    texts = [
        "示例",
        "时之沙",
        "攻击力",
        "18.9%",
        "+0",
        "暴击率+3.9%",
        "暴击伤害+6.2%",
        "防御力+16",
    ]
    result = compat.parse_result(texts)
    assert result["position"] == 3
    assert "'position': 3" in capsys.readouterr().out


def test_legacy_calc_score_roles_returns_pyplot(
    legacy_item: dict[str, object],
) -> None:
    params = {"roles": ["夜兰"], "item": legacy_item, "runs": 2, "seed": 1}
    pyplot = compat.calc_score_roles(params)
    assert hasattr(pyplot, "show")
    pyplot.close("all")


def test_legacy_ocr_uses_local_model_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    image = tmp_path / "card.png"
    image.write_bytes(b"x")

    class Engine:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def read(self, path: Path) -> list[OcrToken]:
            assert path == image
            return [OcrToken(text="时之沙", confidence=1)]

    monkeypatch.setattr(compat, "EasyOcrEngine", Engine)
    result = compat.ocr_item({"item_path": str(image), "model_dir": str(tmp_path)})
    assert result == ["时之沙"]
    assert "时之沙" in capsys.readouterr().out


def test_legacy_warning_is_emitted_once(
    monkeypatch: pytest.MonkeyPatch, legacy_item: dict[str, object]
) -> None:
    monkeypatch.setattr(compat, "_WARNED", False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compat.check_valid(legacy_item)
        compat.check_valid(legacy_item)
    assert len(caught) == 1
    assert issubclass(caught[0].category, FutureWarning)


def test_bundled_data_is_fresh_and_installed_alias_imports() -> None:
    first = compat.bundled_legacy_data()
    first["attrs_choice"]["暴击"] = 0
    assert compat.bundled_legacy_data()["attrs_choice"]["暴击"] == 75
    from calc_item_score.calc_item_score import calc_score

    assert callable(calc_score)


def test_legacy_rule_loaders_fall_back_to_installed_package_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compat, "_LEGACY_DIR", tmp_path / "missing")
    assert compat.load_attrs_choice()["暴击"] == 75
    assert "夜兰" in compat.load_roles_weight()
    with pytest.raises(FileNotFoundError, match="input_param"):
        compat.load_input_param()


def test_legacy_main_calls_show(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[bool] = []
    monkeypatch.setattr(compat, "load_input_param", lambda: {"x": 1})
    monkeypatch.setattr(
        compat,
        "calc_score_roles",
        lambda params: SimpleNamespace(show=lambda: shown.append(True)),
    )
    assert compat.legacy_main() == 0
    assert shown == [True]


def test_legacy_loader_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(ValueError, match="object"):
        compat.load_attrs_weight(path)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"position": 9}, "between 1 and 5"),
        ({"position": "unknown"}, "unknown artifact position"),
        ({"major_attr": "unknown"}, "unknown main attribute"),
        ({"minor_attr": []}, "must be an object"),
    ],
)
def test_legacy_item_conversion_errors(
    legacy_item: dict[str, object], change: dict[str, object], message: str
) -> None:
    raw = copy.deepcopy(legacy_item)
    raw.update(change)
    with pytest.raises(ValueError, match=message):
        legacy_item_to_artifact(raw)


def test_legacy_item_missing_unknown_and_non_numeric_fields(
    legacy_item: dict[str, object],
) -> None:
    missing = copy.deepcopy(legacy_item)
    missing.pop("position")
    with pytest.raises(ValueError, match="missing required"):
        legacy_item_to_artifact(missing)
    unknown = copy.deepcopy(legacy_item)
    unknown["minor_attr"]["未知"] = 1  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown legacy"):
        legacy_item_to_artifact(unknown)
    boolean = copy.deepcopy(legacy_item)
    boolean["minor_attr"]["暴击"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="boolean"):
        legacy_item_to_artifact(boolean)
    text = copy.deepcopy(legacy_item)
    text["minor_attr"]["暴击"] = "x"  # type: ignore[index]
    with pytest.raises(ValueError, match="numeric"):
        legacy_item_to_artifact(text)


def test_legacy_conversion_round_trip_and_stable_position(
    legacy_item: dict[str, object],
) -> None:
    artifact = legacy_item_to_artifact(legacy_item)
    stable = dict(legacy_item)
    stable["position"] = "sands"
    assert legacy_item_to_artifact(stable) == artifact
    assert artifact_to_legacy(artifact)["major_attr"] == "大攻击"


def test_legacy_request_and_mapping_validation(
    legacy_item: dict[str, object],
) -> None:
    request = legacy_request_to_score_request({"roles": ["夜兰"], "item": legacy_item, "runs": 2})
    assert request.runs == 2
    assert "ruleset" not in request.model_fields_set
    with pytest.raises(ValueError, match="requires OCR"):
        legacy_request_to_score_request({"roles": ["夜兰"]})
    with pytest.raises(ValueError, match="must be a list"):
        legacy_request_to_score_request({"roles": "夜兰", "item": legacy_item})
    assert legacy_attribute_mapping({"暴击": "3.9"}) == {AttributeId.CRIT_RATE: Decimal("3.9")}
    with pytest.raises(ValueError, match="unknown"):
        legacy_attribute_mapping({"未知": 1})
