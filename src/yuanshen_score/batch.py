"""Resumable batch execution with failure isolation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from yuanshen_score.config import AppConfig
from yuanshen_score.errors import InputFormatError
from yuanshen_score.io import file_sha256, load_score_request, read_json
from yuanshen_score.models import Artifact, ScoreRequest, StrictModel
from yuanshen_score.ocr import OcrEngine
from yuanshen_score.parser import parse_ocr_tokens
from yuanshen_score.rules import RuleSet
from yuanshen_score.serialization import atomic_write_json, content_sha256
from yuanshen_score.simulation import simulate


class BatchEntry(StrictModel):
    """One independently recoverable batch item."""

    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    input: Path | None = None
    image: Path | None = None
    artifact: Artifact | None = None
    roles: list[str] | None = None
    runs: int | None = Field(default=None, ge=1, le=1_000_000)
    target_level: int | None = Field(default=None, ge=0, le=20)
    seed: int | None = Field(default=None, ge=0, le=18_446_744_073_709_551_615)

    @model_validator(mode="after")
    def exactly_one_source(self) -> BatchEntry:
        count = sum(value is not None for value in (self.input, self.image, self.artifact))
        if count != 1:
            raise ValueError("exactly one of input, image, or artifact is required")
        return self


class BatchRequest(StrictModel):
    """Canonical batch manifest."""

    schema_version: Literal["2.0"] = "2.0"
    roles: list[str] | None = None
    ruleset: str = "legacy-v1"
    runs: int | None = Field(default=None, ge=1, le=1_000_000)
    target_level: int | None = Field(default=None, ge=0, le=20)
    seed: int | None = Field(default=None, ge=0, le=18_446_744_073_709_551_615)
    items: list[BatchEntry] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def unique_ids(cls, value: list[BatchEntry]) -> list[BatchEntry]:
        identifiers = [item.id for item in value]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("batch item ids must be unique")
        return value


def load_batch_request(path: Path) -> BatchRequest:
    """Load a batch manifest and resolve source paths relative to it."""

    raw = read_json(path)
    try:
        request = BatchRequest.model_validate(raw)
    except ValidationError as exc:
        raise InputFormatError(f"批量清单校验失败：{exc}") from exc
    base = path.resolve().parent
    resolved = []
    for item in request.items:
        updates: dict[str, Any] = {}
        if item.input is not None:
            updates["input"] = item.input if item.input.is_absolute() else base / item.input
        if item.image is not None:
            updates["image"] = item.image if item.image.is_absolute() else base / item.image
        resolved.append(item.model_copy(update=updates))
    return request.model_copy(update={"items": resolved})


def _derive_seed(batch_seed: int | None, item: BatchEntry, source_hash: str) -> int | None:
    if item.seed is not None:
        return item.seed
    if batch_seed is None:
        return None
    digest = content_sha256({"seed": batch_seed, "id": item.id, "input": source_hash})
    return int(digest[:16], 16)


def _source_hash(item: BatchEntry) -> str:
    if item.artifact is not None:
        return content_sha256(item.artifact)
    source = item.input or item.image
    if source is None:
        raise AssertionError("validated batch item has no source")
    return file_sha256(source)


def _request_for_item(
    item: BatchEntry,
    batch: BatchRequest,
    config: AppConfig,
    engine: OcrEngine | None,
    *,
    confidence: float,
    accept_low_confidence: bool,
) -> tuple[ScoreRequest, str]:
    source_hash = _source_hash(item)
    embedded: ScoreRequest | None = None
    if item.input is not None:
        embedded = load_score_request(item.input)
        artifact = embedded.artifact
    elif item.image is not None:
        if engine is None:
            raise InputFormatError("批量清单包含截图，但未配置 OCR 引擎")
        parsed = parse_ocr_tokens(
            engine.read(item.image),
            confidence_threshold=confidence,
            accept_low_confidence=accept_low_confidence,
        )
        artifact = parsed.artifact
    elif item.artifact is not None:
        artifact = item.artifact
    else:
        raise AssertionError("validated batch item has no source")

    roles = item.roles or (embedded.roles if embedded else None) or batch.roles
    if not roles:
        raise InputFormatError(f"批量条目 {item.id!r} 未指定角色")
    target = (
        item.target_level
        if item.target_level is not None
        else embedded.target_level
        if embedded and embedded.target_level is not None
        else batch.target_level
        if batch.target_level is not None
        else config.simulation.target_level
    )
    runs = (
        item.runs
        if item.runs is not None
        else embedded.runs
        if embedded and embedded.runs is not None
        else batch.runs
        if batch.runs is not None
        else config.simulation.runs
    )
    seed = _derive_seed(batch.seed, item, source_hash)
    if embedded is not None and item.seed is None and batch.seed is None:
        seed = embedded.seed
    return (
        ScoreRequest(
            artifact=artifact,
            roles=roles,
            ruleset=batch.ruleset,
            runs=runs,
            target_level=target,
            seed=seed,
        ),
        source_hash,
    )


def _safe_error(error: Exception, base: Path) -> str:
    message = str(error)
    replacements = {
        str(base.resolve()): ".",
        str(Path.cwd().resolve()): ".",
        str(Path.home().resolve()): "<HOME>",
    }
    for source, replacement in replacements.items():
        message = message.replace(source, replacement)
    return message


def _result_matches(path: Path, expected_sha256: Any) -> bool:
    if not isinstance(expected_sha256, str) or not path.is_file():
        return False
    try:
        return file_sha256(path) == expected_sha256
    except InputFormatError:
        return False


def run_batch(
    request: BatchRequest,
    *,
    output_dir: Path,
    rule_set: RuleSet,
    config: AppConfig,
    engine: OcrEngine | None = None,
    confidence: float | None = None,
    accept_low_confidence: bool = False,
    resume: bool = False,
    force: bool = False,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Run or resume a batch, persisting state after every item."""

    output_dir = output_dir.resolve()
    state_path = output_dir / "manifest.json"
    if output_dir.exists() and any(output_dir.iterdir()) and not (resume or force):
        raise InputFormatError(f"输出目录非空；请使用新的目录、--resume 或 --force：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if resume:
        if not state_path.is_file():
            raise InputFormatError(f"无法续跑：缺少任务状态文件 {state_path}")
        previous = read_json(state_path)
        if not isinstance(previous, dict):
            raise InputFormatError("任务状态文件顶层必须是对象")
    else:
        previous = {}

    raw_previous_items = (
        previous.get("items", {}) if isinstance(previous.get("items", {}), dict) else {}
    )
    current_ids = {item.id for item in request.items}
    previous_items = {
        identifier: record
        for identifier, record in raw_previous_items.items()
        if identifier in current_ids
    }
    state: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "running",
        "ruleset": rule_set.id,
        "request_sha256": content_sha256(request),
        "started_at": previous.get("started_at", datetime.now(UTC).isoformat()),
        "updated_at": datetime.now(UTC).isoformat(),
        "items": dict(previous_items),
    }
    atomic_write_json(state_path, state)
    threshold = config.ocr.confidence if confidence is None else confidence

    for item in request.items:
        try:
            score_request, source_hash = _request_for_item(
                item,
                request,
                config,
                engine,
                confidence=threshold,
                accept_low_confidence=accept_low_confidence,
            )
            runs = score_request.runs if score_request.runs is not None else config.simulation.runs
            target_level = (
                score_request.target_level
                if score_request.target_level is not None
                else config.simulation.target_level
            )
            execution_sha256 = content_sha256(
                {
                    "source_sha256": source_hash,
                    "artifact": score_request.artifact,
                    "roles": score_request.roles,
                    "ruleset": rule_set.id,
                    "runs": runs,
                    "target_level": target_level,
                    "seed": score_request.seed,
                    "include_raw": include_raw,
                }
            )
            result_name = f"{item.id}.json"
            result_path = output_dir / result_name
            prior = state["items"].get(item.id)
            same_execution = (
                resume
                and isinstance(prior, dict)
                and prior.get("status") == "success"
                and prior.get("input_sha256") == source_hash
                and prior.get("execution_sha256") == execution_sha256
            )
            if same_execution and _result_matches(result_path, prior.get("result_sha256")):
                continue
            simulation_seed = score_request.seed
            if same_execution and simulation_seed is None and isinstance(prior.get("seed"), int):
                simulation_seed = prior["seed"]
            report = simulate(
                score_request.artifact,
                score_request.roles,
                rule_set,
                runs=runs,
                target_level=target_level,
                seed=simulation_seed,
                include_raw=include_raw,
            )
            atomic_write_json(result_path, report)
            state["items"][item.id] = {
                "status": "success",
                "input_sha256": source_hash,
                "execution_sha256": execution_sha256,
                "result": result_name,
                "result_sha256": file_sha256(result_path),
                "seed": report.metadata.seed,
            }
        except Exception as exc:
            state["items"][item.id] = {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": _safe_error(exc, output_dir),
            }
        state["updated_at"] = datetime.now(UTC).isoformat()
        atomic_write_json(state_path, state)

    failures = sum(1 for record in state["items"].values() if record.get("status") == "error")
    state["status"] = "completed_with_errors" if failures else "completed"
    state["failed"] = failures
    state["succeeded"] = len(state["items"]) - failures
    state["updated_at"] = datetime.now(UTC).isoformat()
    atomic_write_json(state_path, state)
    return state
