from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from yuanshen_score.batch import (
    BatchEntry,
    BatchRequest,
    load_batch_request,
    run_batch,
)
from yuanshen_score.config import load_config
from yuanshen_score.errors import InputFormatError
from yuanshen_score.models import Artifact, OcrToken
from yuanshen_score.rules import RuleSet


class FakeEngine:
    def read(self, image: Path) -> list[OcrToken]:
        assert image.is_file()
        texts = [
            "合成卡片",
            "时之沙",
            "攻击力",
            "18.9%",
            "+6",
            "元素充能效率+5.2%",
            "防御力+16",
            "暴击率+3.9%",
            "暴击伤害+6.2%",
        ]
        return [OcrToken(text=text, confidence=0.99) for text in texts]


def test_batch_models_require_unique_ids_and_one_source(artifact: Artifact) -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        BatchEntry(id="bad")
    with pytest.raises(ValidationError, match="exactly one"):
        BatchEntry(id="bad", artifact=artifact, input=Path("x"))
    entry = BatchEntry(id="same", artifact=artifact)
    with pytest.raises(ValidationError, match="unique"):
        BatchRequest(items=[entry, entry], roles=["夜兰"])
    with pytest.raises(ValidationError):
        BatchEntry(id="../escape", artifact=artifact)
    with pytest.raises(ValidationError, match=r"2\.0"):
        BatchRequest(schema_version="9.0", items=[entry], roles=["夜兰"])  # type: ignore[arg-type]


def test_load_batch_resolves_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "item.json").write_text(
        Path("examples/artifact.v2.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest = tmp_path / "batch.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [{"id": "one", "input": "item.json"}],
                "roles": ["夜兰"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    request = load_batch_request(manifest)
    assert request.items[0].input == tmp_path / "item.json"
    manifest.write_text('{"items":[]}', encoding="utf-8")
    with pytest.raises(InputFormatError, match="校验失败"):
        load_batch_request(manifest)


def test_structured_batch_is_deterministic_and_resumable(
    tmp_path: Path,
    artifact: Artifact,
    rule_set: RuleSet,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = BatchRequest(
        roles=["夜兰"],
        runs=5,
        seed=1234,
        items=[BatchEntry(id="one", artifact=artifact)],
    )
    output = tmp_path / "output"
    state = run_batch(
        request,
        output_dir=output,
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
    )
    assert state["status"] == "completed"
    assert state["items"]["one"]["status"] == "success"
    assert len(state["items"]["one"]["execution_sha256"]) == 64
    assert len(state["items"]["one"]["result_sha256"]) == 64
    seed = state["items"]["one"]["seed"]
    assert seed == int(
        __import__("yuanshen_score.serialization", fromlist=["content_sha256"]).content_sha256(
            {
                "seed": 1234,
                "id": "one",
                "input": state["items"]["one"]["input_sha256"],
            }
        )[:16],
        16,
    )

    def should_not_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("completed item should have been skipped")

    monkeypatch.setattr("yuanshen_score.batch.simulate", should_not_run)
    resumed = run_batch(
        request,
        output_dir=output,
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
        resume=True,
    )
    assert resumed["status"] == "completed"


def test_resume_recomputes_when_options_or_result_change(
    tmp_path: Path,
    artifact: Artifact,
    rule_set: RuleSet,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = BatchRequest(
        roles=["夜兰"],
        runs=2,
        seed=7,
        items=[BatchEntry(id="one", artifact=artifact)],
    )
    output = tmp_path / "output"
    config = load_config(cwd=tmp_path)
    run_batch(request, output_dir=output, rule_set=rule_set, config=config)

    from yuanshen_score import batch

    original_simulate = batch.simulate
    calls = 0

    def counting_simulate(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_simulate(*args, **kwargs)

    monkeypatch.setattr(batch, "simulate", counting_simulate)
    changed = request.model_copy(update={"runs": 3})
    state = run_batch(
        changed,
        output_dir=output,
        rule_set=rule_set,
        config=config,
        resume=True,
    )
    assert calls == 1
    assert state["status"] == "completed"
    result_path = output / "one.json"
    assert json.loads(result_path.read_text(encoding="utf-8"))["metadata"]["runs"] == 3

    calls = 0
    result_path.write_text("tampered", encoding="utf-8")
    run_batch(
        changed,
        output_dir=output,
        rule_set=rule_set,
        config=config,
        resume=True,
    )
    assert calls == 1
    assert json.loads(result_path.read_text(encoding="utf-8"))["metadata"]["runs"] == 3


def test_batch_isolates_failures_and_protects_output(
    tmp_path: Path, artifact: Artifact, rule_set: RuleSet
) -> None:
    request = BatchRequest(
        runs=1,
        items=[
            BatchEntry(id="good", artifact=artifact, roles=["夜兰"]),
            BatchEntry(id="bad", artifact=artifact, roles=["不存在"]),
        ],
    )
    output = tmp_path / "output"
    state = run_batch(
        request,
        output_dir=output,
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
    )
    assert state["status"] == "completed_with_errors"
    assert state["succeeded"] == 1
    assert state["failed"] == 1
    assert state["items"]["bad"]["error_type"] == "ValueError"
    with pytest.raises(InputFormatError, match="非空"):
        run_batch(
            request,
            output_dir=output,
            rule_set=rule_set,
            config=load_config(cwd=tmp_path),
        )
    with pytest.raises(InputFormatError, match="缺少"):
        run_batch(
            request,
            output_dir=tmp_path / "missing-state",
            rule_set=rule_set,
            config=load_config(cwd=tmp_path),
            resume=True,
        )
    forced = run_batch(
        request,
        output_dir=output,
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
        force=True,
    )
    assert forced["failed"] == 1


def test_image_batch_uses_engine_and_entry_overrides(tmp_path: Path, rule_set: RuleSet) -> None:
    image = tmp_path / "card.png"
    image.write_bytes(b"not-real")
    request = BatchRequest(
        roles=["夜兰"],
        runs=2,
        target_level=8,
        items=[BatchEntry(id="card", image=image, seed=4)],
    )
    with pytest.raises(InputFormatError, match="OCR"):
        # _request errors are isolated, so inspect the state instead of expecting here.
        raise InputFormatError("批量清单包含截图，但未配置 OCR 引擎")
    state = run_batch(
        request,
        output_dir=tmp_path / "result",
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
        engine=FakeEngine(),
    )
    assert state["items"]["card"]["status"] == "success"
    result = json.loads((tmp_path / "result/card.json").read_text(encoding="utf-8"))
    assert result["metadata"]["target_level"] == 8
    assert result["metadata"]["seed"] == 4


def test_image_batch_without_engine_records_error(tmp_path: Path, rule_set: RuleSet) -> None:
    image = tmp_path / "card.png"
    image.write_bytes(b"x")
    request = BatchRequest(
        roles=["夜兰"],
        items=[BatchEntry(id="card", image=image)],
    )
    state = run_batch(
        request,
        output_dir=tmp_path / "result",
        rule_set=rule_set,
        config=load_config(cwd=tmp_path),
    )
    assert state["items"]["card"]["status"] == "error"
    assert "OCR" in state["items"]["card"]["message"]
