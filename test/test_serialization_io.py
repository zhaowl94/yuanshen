from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from yuanshen_score.constants import AttributeId
from yuanshen_score.errors import InputFormatError
from yuanshen_score.io import (
    file_sha256,
    load_score_request,
    read_input_object,
    read_json,
    report_csv,
    write_output,
)
from yuanshen_score.models import Artifact
from yuanshen_score.rules import RuleSet
from yuanshen_score.scoring import build_score_report
from yuanshen_score.serialization import (
    atomic_write_text,
    canonical_json,
    content_sha256,
    decimal_number,
    json_ready,
    pretty_json,
)
from yuanshen_score.simulation import simulate


def test_decimal_serialization_rounds_half_even() -> None:
    assert decimal_number(Decimal("2.0000001")) == 2
    assert decimal_number(Decimal("1.2345675")) == 1.234568
    assert decimal_number(Decimal("1.2345665")) == 1.234566


def test_json_ready_supports_domain_values(tmp_path: Path) -> None:
    value = {
        AttributeId.CRIT_RATE: Decimal("3.9"),
        "path": tmp_path,
        "time": datetime(2026, 1, 2, tzinfo=UTC),
        "tuple": (Decimal("1"),),
    }
    ready = json_ready(value)
    assert ready["crit_rate"] == 3.9
    assert ready["path"] == str(tmp_path)
    assert ready["time"] == "2026-01-02T00:00:00+00:00"
    assert ready["tuple"] == [1]


def test_canonical_and_pretty_json_are_stable() -> None:
    left = {"b": Decimal("2"), "a": 1}
    right = {"a": 1, "b": Decimal("2.0")}
    assert canonical_json(left) == canonical_json(right) == '{"a":1,"b":2}'
    assert content_sha256(left) == content_sha256(right)
    assert pretty_json(left).endswith("\n")


def test_atomic_write_replaces_and_cleans_temp_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "value.txt"
    atomic_write_text(target, "first")
    assert target.read_text(encoding="utf-8") == "first"

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("boom")

    monkeypatch.setattr("yuanshen_score.serialization.os.replace", fail_replace)
    with pytest.raises(OSError, match="boom"):
        atomic_write_text(target, "second")
    assert target.read_text(encoding="utf-8") == "first"
    assert list(tmp_path.glob("*.tmp")) == []


def test_load_new_and_legacy_requests(tmp_path: Path, legacy_item: dict[str, object]) -> None:
    new_request = load_score_request(Path("examples/artifact.v2.json"))
    assert new_request.artifact.main_attribute == "atk_percent"
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        json.dumps({"roles": ["夜兰"], "item": legacy_item}, ensure_ascii=False),
        encoding="utf-8",
    )
    legacy = load_score_request(legacy_path)
    assert legacy.roles == ["夜兰"]
    assert legacy.artifact.substats[AttributeId.CRIT_RATE] == Decimal("3.9")


def test_input_errors_include_location(tmp_path: Path) -> None:
    with pytest.raises(InputFormatError, match="无法读取"):
        read_json(tmp_path / "missing.json")
    invalid = tmp_path / "bad.json"
    invalid.write_text("{\n", encoding="utf-8")
    with pytest.raises(InputFormatError, match=r":2:1"):
        read_json(invalid)
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(InputFormatError, match="顶层"):
        load_score_request(array)
    with pytest.raises(InputFormatError, match="顶层"):
        read_input_object(array)
    no_item = tmp_path / "no-item.json"
    no_item.write_text('{"roles":["夜兰"]}', encoding="utf-8")
    with pytest.raises(InputFormatError, match="requires OCR"):
        load_score_request(no_item)


def test_file_hash_and_error(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")
    assert file_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    with pytest.raises(InputFormatError, match="无法读取"):
        file_sha256(tmp_path / "missing")


def test_json_and_csv_output_contracts(
    tmp_path: Path, artifact: Artifact, rule_set: RuleSet
) -> None:
    score = build_score_report(artifact, ["夜兰"], rule_set)
    score_csv = report_csv(score)
    assert score_csv.startswith("role,current_score\n夜兰,")
    simulation = simulate(artifact, ["夜兰"], rule_set, runs=2, seed=1)
    simulation_csv = report_csv(simulation)
    assert "minimum,q1,median,mean,q3,maximum,runs,seed" in simulation_csv
    path = tmp_path / "result.json"
    write_output(path, score)
    assert json.loads(path.read_text(encoding="utf-8"))["scores"][0]["role"] == "夜兰"
    with pytest.raises(InputFormatError, match="--force"):
        write_output(path, score)
    write_output(path, score, force=True)
    csv_path = tmp_path / "result.csv"
    write_output(csv_path, simulation, as_csv=True)
    assert csv_path.read_text(encoding="utf-8").startswith("role,current_score")
    with pytest.raises(TypeError, match="only supports"):
        write_output(tmp_path / "bad.csv", {"x": 1}, as_csv=True)
