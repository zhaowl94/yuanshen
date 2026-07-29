"""Optional EasyOCR adapter and explicit model management."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Protocol, cast

from yuanshen_score.errors import OcrDependencyError, OcrModelError
from yuanshen_score.models import OcrToken
from yuanshen_score.serialization import atomic_write_json

_MANIFEST_NAME = "manifest.json"


class OcrEngine(Protocol):
    """Engine-neutral OCR protocol."""

    def read(self, image: Path) -> list[OcrToken]:
        """Recognize an image into positioned, confidence-bearing tokens."""


def _easyocr_module() -> Any:
    try:
        import easyocr
    except ImportError as exc:
        raise OcrDependencyError(
            "EasyOCR 未安装；请安装 yuanshen-score[ocr]，"
            "Windows 用户还应先按 PyTorch 官方指引安装匹配的 CPU/CUDA 版本"
        ) from exc
    return easyocr


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_files(model_dir: Path) -> list[Path]:
    return sorted(
        path for path in model_dir.rglob("*") if path.is_file() and path.name != _MANIFEST_NAME
    )


def install_easyocr_models(
    model_dir: Path, *, languages: tuple[str, ...] = ("ch_sim", "en")
) -> dict[str, Any]:
    """Explicitly download EasyOCR models and record their checksums."""

    easyocr = _easyocr_module()
    model_dir = model_dir.resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    easyocr.Reader(
        list(languages),
        gpu=False,
        model_storage_directory=str(model_dir),
        download_enabled=True,
        verbose=False,
    )
    files = _model_files(model_dir)
    if not files:
        raise OcrModelError(f"EasyOCR 未在模型目录中创建文件：{model_dir}")
    manifest = {
        "schema_version": "1.0",
        "engine": "easyocr",
        "engine_version": importlib.metadata.version("easyocr"),
        "languages": list(languages),
        "files": [
            {
                "path": path.relative_to(model_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for path in files
        ],
    }
    atomic_write_json(model_dir / _MANIFEST_NAME, manifest)
    return manifest


def verify_easyocr_models(model_dir: Path) -> dict[str, Any]:
    """Verify every model file against the locally recorded install manifest."""

    model_dir = model_dir.resolve()
    manifest_path = model_dir / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise OcrModelError(
            f"未找到 OCR 模型清单：{manifest_path}；"
            "请先运行 yuanshen-score models install easyocr-zh"
        )
    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw_manifest, dict):
            raise TypeError("manifest root is not an object")
        manifest = cast(dict[str, Any], raw_manifest)
        records = manifest["files"]
        if not isinstance(records, list):
            raise TypeError("manifest files is not a list")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OcrModelError(f"OCR 模型清单无效：{manifest_path}") from exc
    for record in records:
        if not isinstance(record, dict):
            raise OcrModelError("OCR 模型清单包含无效文件记录")
        path = (model_dir / record["path"]).resolve()
        if model_dir not in path.parents:
            raise OcrModelError(f"OCR 模型清单包含越界路径：{record['path']!r}")
        if not path.is_file():
            raise OcrModelError(f"OCR 模型文件缺失：{path}")
        if path.stat().st_size != record["size"] or _sha256_file(path) != record["sha256"]:
            raise OcrModelError(f"OCR 模型校验失败：{path}")
    return manifest


class EasyOcrEngine:
    """Lazy, reusable EasyOCR implementation."""

    def __init__(
        self,
        model_dir: Path,
        *,
        device: str = "cpu",
        languages: tuple[str, ...] = ("ch_sim", "en"),
    ) -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError("OCR device must be 'cpu' or 'cuda'")
        self.model_dir = model_dir.resolve()
        self.device = device
        self.languages = languages
        self._reader: Any | None = None

    def _get_reader(self) -> Any:
        if self._reader is None:
            verify_easyocr_models(self.model_dir)
            easyocr = _easyocr_module()
            try:
                self._reader = easyocr.Reader(
                    list(self.languages),
                    gpu=self.device == "cuda",
                    model_storage_directory=str(self.model_dir),
                    download_enabled=False,
                    verbose=False,
                )
            except Exception as exc:
                raise OcrModelError(f"无法加载 EasyOCR 模型：{exc}") from exc
        return self._reader

    def read(self, image: Path) -> list[OcrToken]:
        image = image.resolve()
        if not image.is_file():
            raise OcrModelError(f"截图文件不存在：{image}")
        try:
            raw = self._get_reader().readtext(str(image), detail=1)
        except OcrModelError:
            raise
        except Exception as exc:
            raise OcrModelError(f"EasyOCR 识别失败：{exc}") from exc
        tokens: list[OcrToken] = []
        for bounding_box, text, confidence in raw:
            raw_box = tuple(
                tuple(float(coordinate) for coordinate in point) for point in bounding_box
            )
            if len(raw_box) != 4 or any(len(point) != 2 for point in raw_box):
                raise OcrModelError("EasyOCR 返回了无效的文字边界框")
            box = cast(
                tuple[
                    tuple[float, float],
                    tuple[float, float],
                    tuple[float, float],
                    tuple[float, float],
                ],
                raw_box,
            )
            tokens.append(
                OcrToken(
                    text=str(text),
                    confidence=float(confidence),
                    bounding_box=box,
                )
            )
        return tokens
