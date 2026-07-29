"""Canonical serialization, hashing, and atomic file writes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_OUTPUT_QUANTUM = Decimal("0.000001")


def decimal_number(value: Decimal) -> int | float:
    """Convert a Decimal to a JSON number with at most six decimal places."""

    rounded = value.quantize(_OUTPUT_QUANTUM, rounding=ROUND_HALF_EVEN)
    if rounded == rounded.to_integral():
        return int(rounded)
    return float(rounded)


def json_ready(value: Any) -> Any:
    """Recursively convert supported domain values into JSON-safe values."""

    if isinstance(value, BaseModel):
        return json_ready(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        return decimal_number(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(json_ready(key)): json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_ready(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Return deterministic compact JSON for hashing and fixtures."""

    return json.dumps(
        json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_sha256(value: Any) -> str:
    """Hash canonical JSON content."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def pretty_json(value: Any) -> str:
    """Return human-readable, stable UTF-8 JSON."""

    return (
        json.dumps(
            json_ready(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a text file without leaving partial output."""

    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    """Atomically write pretty JSON."""

    atomic_write_text(path, pretty_json(value))
