from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import matplotlib
import pytest

from yuanshen_score.constants import AttributeId, PositionId
from yuanshen_score.models import Artifact, OcrToken
from yuanshen_score.rules import RuleSet, load_rule_set

matplotlib.use("Agg", force=True)


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Workspace-local replacement for pytest's ACL-sensitive Windows fixture."""

    root = Path(".test-work").resolve()
    root.mkdir(exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        if path.parent == root:
            shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def artifact() -> Artifact:
    return Artifact(
        position=PositionId.SANDS,
        main_attribute="atk_percent",
        level=6,
        rarity=5,
        substats={
            AttributeId.FLAT_DEF: Decimal("16"),
            AttributeId.ENERGY_RECHARGE: Decimal("5.2"),
            AttributeId.CRIT_RATE: Decimal("3.9"),
            AttributeId.CRIT_DAMAGE: Decimal("6.2"),
        },
        name="合成示例",
    )


@pytest.fixture
def three_stat_artifact() -> Artifact:
    return Artifact(
        position=PositionId.SANDS,
        main_attribute="atk_percent",
        level=0,
        substats={
            AttributeId.ENERGY_RECHARGE: Decimal("5.2"),
            AttributeId.CRIT_RATE: Decimal("3.9"),
            AttributeId.CRIT_DAMAGE: Decimal("6.2"),
        },
    )


@pytest.fixture(scope="session")
def rule_set() -> RuleSet:
    return load_rule_set()


@pytest.fixture
def legacy_item() -> dict[str, object]:
    return {
        "position": 3,
        "major_attr": "大攻击",
        "level": 6,
        "minor_attr": {
            "小生命": 0,
            "小攻击": 0,
            "小防御": 16,
            "精通": 0,
            "充能": 5.2,
            "大生命": 0,
            "大攻击": 0,
            "大防御": 0,
            "暴击": 3.9,
            "爆伤": 6.2,
        },
    }


@pytest.fixture
def sample_tokens() -> list[OcrToken]:
    texts = [
        "终幕的时计",
        "时之沙",
        "攻击力",
        "18.9%",
        "+6",
        "· 元素充能效率+5.2%",
        "· 防御力+16",
        "· 暴击率+3.9%",
        "· 暴击伤害+6.2%",
    ]
    return [OcrToken(text=text, confidence=0.99) for text in texts]
