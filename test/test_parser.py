from __future__ import annotations

from decimal import Decimal

import pytest

from yuanshen_score.constants import AttributeId, PositionId
from yuanshen_score.errors import LowConfidenceError, OcrParseError
from yuanshen_score.models import OcrToken
from yuanshen_score.parser import (
    normalize_ocr_text,
    parse_legacy_texts,
    parse_ocr_tokens,
)


def test_parse_cropped_card(sample_tokens: list[OcrToken]) -> None:
    result = parse_ocr_tokens(sample_tokens)
    assert result.artifact.position is PositionId.SANDS
    assert result.artifact.main_attribute == "atk_percent"
    assert result.artifact.level == 6
    assert result.artifact.name == "终幕的时计"
    assert result.artifact.substats[AttributeId.ENERGY_RECHARGE] == Decimal("5.2")
    assert len(result.relevant_tokens) == 7


def test_parser_joins_split_substat_tokens(sample_tokens: list[OcrToken]) -> None:
    split = [
        *sample_tokens[:5],
        OcrToken(text="元素充能效率", confidence=0.9),
        OcrToken(text="+5.2%", confidence=0.8),
        *sample_tokens[6:],
    ]
    result = parse_ocr_tokens(split)
    token = next(token for token in result.relevant_tokens if "元素充能效率" in token.text)
    assert token.confidence == 0.8


@pytest.mark.parametrize(
    ("position", "main_label", "expected"),
    [
        ("生之花", "生命值", "flat_hp"),
        ("死之羽", "攻击力", "flat_atk"),
        ("时之沙", "元素精通", "elemental_mastery"),
        ("时之沙", "元素充能效率", "energy_recharge"),
        ("空之杯", "火元素伤害加成", "pyro_damage_bonus"),
        ("理之冠", "治疗加成", "healing_bonus"),
    ],
)
def test_position_specific_main_attributes(position: str, main_label: str, expected: str) -> None:
    tokens = [
        OcrToken(text="示例", confidence=1),
        OcrToken(text=position, confidence=1),
        OcrToken(text=main_label, confidence=1),
        OcrToken(text="18.9%", confidence=1),
        OcrToken(text="+0", confidence=1),
        OcrToken(text="暴击率+3.9%", confidence=1),
        OcrToken(text="暴击伤害+6.2%", confidence=1),
        OcrToken(text="防御力+16", confidence=1),
    ]
    assert parse_ocr_tokens(tokens).artifact.main_attribute == expected


def test_percentage_and_flat_substats_are_distinct() -> None:
    texts = [
        "示例",
        "时之沙",
        "元素精通",
        "187",
        "+0",
        "生命值+5.8%",
        "攻击力+19",
        "防御力+7.3%",
    ]
    artifact = parse_legacy_texts(texts)
    assert set(artifact.substats) == {
        AttributeId.HP_PERCENT,
        AttributeId.FLAT_ATK,
        AttributeId.DEF_PERCENT,
    }


def test_low_confidence_stops_or_warns(sample_tokens: list[OcrToken]) -> None:
    tokens = list(sample_tokens)
    tokens[6] = tokens[6].model_copy(update={"confidence": 0.2})
    with pytest.raises(LowConfidenceError, match=r"0\.20"):
        parse_ocr_tokens(tokens, confidence_threshold=0.65)
    result = parse_ocr_tokens(tokens, confidence_threshold=0.65, accept_low_confidence=True)
    assert result.warnings and "0.20" in result.warnings[0]


@pytest.mark.parametrize(
    ("tokens", "message"),
    [
        ([], "任何文字"),
        ([OcrToken(text="无部位", confidence=1)], "部位"),
        (
            [
                OcrToken(text="时之沙", confidence=1),
                OcrToken(text="攻击力", confidence=1),
            ],
            "等级",
        ),
        (
            [
                OcrToken(text="时之沙", confidence=1),
                OcrToken(text="未知主词条", confidence=1),
                OcrToken(text="+0", confidence=1),
                OcrToken(text="暴击率+3.9%", confidence=1),
                OcrToken(text="暴击伤害+6.2%", confidence=1),
                OcrToken(text="防御力+16", confidence=1),
            ],
            "主词条",
        ),
        (
            [
                OcrToken(text="生之花", confidence=1),
                OcrToken(text="4780", confidence=1),
                OcrToken(text="+0", confidence=1),
                OcrToken(text="暴击率+3.9%", confidence=1),
                OcrToken(text="暴击伤害+6.2%", confidence=1),
                OcrToken(text="防御力+16", confidence=1),
            ],
            "主词条",
        ),
    ],
)
def test_parser_reports_missing_required_fields(tokens: list[OcrToken], message: str) -> None:
    with pytest.raises(OcrParseError, match=message):
        parse_ocr_tokens(tokens)


def test_parser_rejects_wrong_count_and_duplicates(
    sample_tokens: list[OcrToken],
) -> None:
    with pytest.raises(OcrParseError, match="实际识别到 2"):
        parse_ocr_tokens(sample_tokens[:-2])
    with pytest.raises(OcrParseError, match=r"\+4 及以上"):
        parse_ocr_tokens(sample_tokens[:-1])
    duplicate = [*sample_tokens, OcrToken(text="暴击率+2.7%", confidence=1)]
    with pytest.raises(OcrParseError, match="重复"):
        parse_ocr_tokens(duplicate)


def test_parser_validates_threshold(sample_tokens: list[OcrToken]) -> None:
    with pytest.raises(ValueError, match="between"):
        parse_ocr_tokens(sample_tokens, confidence_threshold=2)


def test_normalization_only_handles_typography() -> None:
    assert normalize_ocr_text(" · 暴击率 ＋ 3.9％ ") == "暴击率+3.9%"


@pytest.mark.parametrize(
    ("mistaken", "corrected"),
    [
        ("元素充能效宰+5.8%", "元素充能效率+5.8%"),
        ("暴击宰+7.4%", "暴击率+7.4%"),
        ("疑击伤害+6.2%", "暴击伤害+6.2%"),
        ("无素精通+16", "元素精通+16"),
    ],
)
def test_known_ocr_confusions_are_audited(
    sample_tokens: list[OcrToken], mistaken: str, corrected: str
) -> None:
    tokens = [
        *sample_tokens[:5],
        OcrToken(text=mistaken, confidence=0.99),
        OcrToken(text="防御力+16", confidence=0.99),
        OcrToken(text="攻击力+19", confidence=0.99),
        OcrToken(text="生命值+239", confidence=0.99),
    ]
    result = parse_ocr_tokens(tokens)
    assert any(mistaken.split("+")[0] in warning for warning in result.warnings)
    assert any(token.text == corrected for token in result.relevant_tokens)


def test_unparsed_substat_like_token_never_fails_silently(
    sample_tokens: list[OcrToken],
) -> None:
    tokens = [
        *sample_tokens[:5],
        OcrToken(text="未知属性+5.2%", confidence=0.99),
        *sample_tokens[6:],
    ]
    with pytest.raises(OcrParseError, match="疑似副词条"):
        parse_ocr_tokens(tokens, accept_low_confidence=True)
