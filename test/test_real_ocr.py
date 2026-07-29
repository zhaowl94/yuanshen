from __future__ import annotations

from pathlib import Path

import pytest

from yuanshen_score.ocr import EasyOcrEngine


@pytest.mark.real_ocr
def test_real_easyocr_cpu_inference() -> None:
    """Run only after the explicit model-install step has created a manifest."""

    model_dir = Path(".yuanshen-score/models").resolve()
    if not (model_dir / "manifest.json").is_file():
        pytest.skip(
            "real OCR models are not installed; run yuanshen-score models install easyocr-zh first"
        )

    from PIL import Image, ImageDraw, ImageFont

    image_path = Path(".test-work/real-ocr-card.png").resolve()
    image_path.parent.mkdir(exist_ok=True)
    image = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 72)
    except OSError:
        font = ImageFont.load_default(size=48)
    draw.text((35, 55), "ARTIFACT 123", fill="black", font=font)
    image.save(image_path)
    try:
        tokens = EasyOcrEngine(model_dir, device="cpu").read(image_path)
        assert tokens
        assert any(token.confidence > 0 for token in tokens)
    finally:
        image_path.unlink(missing_ok=True)
