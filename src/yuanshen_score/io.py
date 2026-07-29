"""Input and output contracts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from yuanshen_score.errors import InputFormatError
from yuanshen_score.legacy import legacy_request_to_score_request
from yuanshen_score.models import ScoreReport, ScoreRequest, SimulationReport
from yuanshen_score.serialization import atomic_write_text, json_ready, pretty_json


def read_json(path: Path) -> Any:
    """Read UTF-8 JSON while preserving decimal source values."""

    path = path.resolve()
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle, parse_float=Decimal)
    except OSError as exc:
        raise InputFormatError(f"无法读取输入文件：{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputFormatError(
            f"JSON 格式错误：{path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc


def load_score_request(path: Path) -> ScoreRequest:
    """Load canonical v2 JSON or a historical input containing ``item``."""

    raw = read_json(path)
    if not isinstance(raw, Mapping):
        raise InputFormatError("输入 JSON 顶层必须是对象")
    try:
        if raw.get("schema_version") == "2.0" or "artifact" in raw:
            return ScoreRequest.model_validate(raw)
        return legacy_request_to_score_request(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        raise InputFormatError(f"输入校验失败：{exc}") from exc


def read_input_object(path: Path) -> dict[str, Any]:
    """Load a top-level object for the combined OCR/run workflow."""

    raw = read_json(path)
    if not isinstance(raw, dict):
        raise InputFormatError("输入 JSON 顶层必须是对象")
    return raw


def file_sha256(path: Path) -> str:
    """Hash file bytes without exposing its local path."""

    digest = hashlib.sha256()
    try:
        with path.resolve().open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise InputFormatError(f"无法读取输入文件：{path.name}: {exc}") from exc
    return digest.hexdigest()


def report_csv(report: ScoreReport | SimulationReport) -> str:
    """Create a stable CSV summary."""

    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    if isinstance(report, ScoreReport):
        writer.writerow(["role", "current_score"])
        for score in report.scores:
            writer.writerow([score.role, json_ready(score.score)])
    else:
        writer.writerow(
            [
                "role",
                "current_score",
                "minimum",
                "q1",
                "median",
                "mean",
                "q3",
                "maximum",
                "runs",
                "seed",
            ]
        )
        for result in report.results:
            summary = result.final_score
            writer.writerow(
                [
                    result.role,
                    json_ready(result.current_score),
                    json_ready(summary.minimum),
                    json_ready(summary.q1),
                    json_ready(summary.median),
                    json_ready(summary.mean),
                    json_ready(summary.q3),
                    json_ready(summary.maximum),
                    report.metadata.runs,
                    report.metadata.seed,
                ]
            )
    return stream.getvalue()


def write_output(
    path: Path,
    value: Any,
    *,
    force: bool = False,
    as_csv: bool = False,
) -> None:
    """Write one output atomically, requiring opt-in replacement."""

    path = path.resolve()
    if path.exists() and not force:
        raise InputFormatError(f"输出文件已存在；如需覆盖请显式使用 --force：{path}")
    if as_csv:
        if not isinstance(value, (ScoreReport, SimulationReport)):
            raise TypeError("CSV output only supports score and simulation reports")
        content = report_csv(value)
    else:
        content = pretty_json(value)
    atomic_write_text(path, content)
