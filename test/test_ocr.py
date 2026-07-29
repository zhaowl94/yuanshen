from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from yuanshen_score.errors import OcrDependencyError, OcrModelError
from yuanshen_score.ocr import (
    EasyOcrEngine,
    _easyocr_module,
    install_easyocr_models,
    verify_easyocr_models,
)


class FakeReader:
    created = 0
    fail_init = False
    fail_read = False
    invalid_box = False

    def __init__(
        self,
        languages: list[str],
        *,
        gpu: bool,
        model_storage_directory: str,
        download_enabled: bool,
        verbose: bool,
    ) -> None:
        del languages, gpu, verbose
        type(self).created += 1
        if self.fail_init:
            raise RuntimeError("reader init")
        if download_enabled:
            model = Path(model_storage_directory) / "model.bin"
            model.parent.mkdir(parents=True, exist_ok=True)
            model.write_bytes(b"model")

    def readtext(self, image: str, *, detail: int) -> list[tuple[object, str, float]]:
        del image, detail
        if self.fail_read:
            raise RuntimeError("reader read")
        box: object = [[0, 0], [2, 0], [2, 1], [0, 1]]
        if self.invalid_box:
            box = [[0, 0]]
        return [(box, "攻击力", 0.9)]


@pytest.fixture(autouse=True)
def reset_reader() -> None:
    FakeReader.created = 0
    FakeReader.fail_init = False
    FakeReader.fail_read = False
    FakeReader.invalid_box = False


def test_missing_easyocr_dependency_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = __import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "easyocr":
            raise ImportError("blocked")
        return original(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(OcrDependencyError, match=r"yuanshen-score\[ocr\]"):
        _easyocr_module()


def test_model_install_and_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(Reader=FakeReader)
    monkeypatch.setattr("yuanshen_score.ocr._easyocr_module", lambda: fake)
    monkeypatch.setattr("yuanshen_score.ocr.importlib.metadata.version", lambda name: "1.7.2")
    manifest = install_easyocr_models(tmp_path)
    assert manifest["engine_version"] == "1.7.2"
    assert manifest["files"][0]["sha256"]
    assert verify_easyocr_models(tmp_path) == manifest


@pytest.mark.parametrize("mode", ["missing", "invalid-json", "root-array", "files-not-list"])
def test_model_manifest_errors(tmp_path: Path, mode: str) -> None:
    manifest = tmp_path / "manifest.json"
    if mode == "invalid-json":
        manifest.write_text("{", encoding="utf-8")
    elif mode == "root-array":
        manifest.write_text("[]", encoding="utf-8")
    elif mode == "files-not-list":
        manifest.write_text('{"files":{}}', encoding="utf-8")
    with pytest.raises(OcrModelError):
        verify_easyocr_models(tmp_path)


def test_model_verification_detects_missing_tampered_and_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = SimpleNamespace(Reader=FakeReader)
    monkeypatch.setattr("yuanshen_score.ocr._easyocr_module", lambda: fake)
    monkeypatch.setattr("yuanshen_score.ocr.importlib.metadata.version", lambda name: "1")
    install_easyocr_models(tmp_path)
    (tmp_path / "model.bin").write_bytes(b"tampered")
    with pytest.raises(OcrModelError, match="校验失败"):
        verify_easyocr_models(tmp_path)
    (tmp_path / "model.bin").unlink()
    with pytest.raises(OcrModelError, match="缺失"):
        verify_easyocr_models(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = [{"path": "../outside", "size": 0, "sha256": ""}]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OcrModelError, match="越界"):
        verify_easyocr_models(tmp_path)


def test_install_requires_created_model_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class EmptyReader(FakeReader):
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setattr(
        "yuanshen_score.ocr._easyocr_module", lambda: SimpleNamespace(Reader=EmptyReader)
    )
    with pytest.raises(OcrModelError, match="创建文件"):
        install_easyocr_models(tmp_path)


def _installed_fake_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EasyOcrEngine:
    fake = SimpleNamespace(Reader=FakeReader)
    monkeypatch.setattr("yuanshen_score.ocr._easyocr_module", lambda: fake)
    monkeypatch.setattr("yuanshen_score.ocr.importlib.metadata.version", lambda name: "1")
    install_easyocr_models(tmp_path)
    return EasyOcrEngine(tmp_path)


def test_engine_is_lazy_and_reuses_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _installed_fake_engine(tmp_path, monkeypatch)
    baseline = FakeReader.created
    image = tmp_path / "image.png"
    image.write_bytes(b"fake")
    first = engine.read(image)
    second = engine.read(image)
    assert FakeReader.created == baseline + 1
    assert first == second
    assert first[0].bounding_box == ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0))


def test_engine_validates_device_and_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="cpu"):
        EasyOcrEngine(tmp_path, device="metal")
    engine = _installed_fake_engine(tmp_path, monkeypatch)
    with pytest.raises(OcrModelError, match="不存在"):
        engine.read(tmp_path / "missing.png")


def test_engine_wraps_reader_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"x")
    engine = _installed_fake_engine(tmp_path, monkeypatch)
    FakeReader.fail_init = True
    with pytest.raises(OcrModelError, match="无法加载"):
        engine.read(image)
    FakeReader.fail_init = False
    engine = EasyOcrEngine(tmp_path)
    FakeReader.fail_read = True
    with pytest.raises(OcrModelError, match="识别失败"):
        engine.read(image)
    FakeReader.fail_read = False
    engine = EasyOcrEngine(tmp_path)
    FakeReader.invalid_box = True
    with pytest.raises(OcrModelError, match="边界框"):
        engine.read(image)
