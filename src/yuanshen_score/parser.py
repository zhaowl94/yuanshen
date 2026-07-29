"""Simplified-Chinese artifact card parsing."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from yuanshen_score.constants import POSITION_LABELS_ZH, AttributeId, PositionId
from yuanshen_score.errors import LowConfidenceError, OcrParseError
from yuanshen_score.models import Artifact, OcrParseResult, OcrToken

_POSITION_BY_LABEL = {label: position for position, label in POSITION_LABELS_ZH.items()}
_SUBSTAT_NAMES = {
    "生命值",
    "攻击力",
    "防御力",
    "元素精通",
    "元素充能效率",
    "暴击率",
    "暴击伤害",
}
_SUBSTAT_PATTERN = re.compile(
    r"^(生命值|攻击力|防御力|元素精通|元素充能效率|暴击率|暴击伤害)"
    r"\+([0-9]+(?:\.[0-9]+)?)(%)?$"
)
_LEVEL_PATTERN = re.compile(r"^\+?([0-9]{1,2})$")
_KNOWN_OCR_CORRECTIONS = {
    "元素充能效宰": "元素充能效率",
    "暴击宰": "暴击率",
    "疑击伤害": "暴击伤害",
    "无素精通": "元素精通",
}

_MAIN_BY_POSITION: dict[PositionId, dict[str, str]] = {
    PositionId.FLOWER: {"生命值": "flat_hp"},
    PositionId.PLUME: {"攻击力": "flat_atk"},
    PositionId.SANDS: {
        "生命值": "hp_percent",
        "防御力": "def_percent",
        "攻击力": "atk_percent",
        "元素精通": "elemental_mastery",
        "元素充能效率": "energy_recharge",
    },
    PositionId.GOBLET: {
        "生命值": "hp_percent",
        "防御力": "def_percent",
        "攻击力": "atk_percent",
        "元素精通": "elemental_mastery",
        "物理伤害加成": "physical_damage_bonus",
        "火元素伤害加成": "pyro_damage_bonus",
        "水元素伤害加成": "hydro_damage_bonus",
        "草元素伤害加成": "dendro_damage_bonus",
        "雷元素伤害加成": "electro_damage_bonus",
        "风元素伤害加成": "anemo_damage_bonus",
        "冰元素伤害加成": "cryo_damage_bonus",
        "岩元素伤害加成": "geo_damage_bonus",
    },
    PositionId.CIRCLET: {
        "生命值": "hp_percent",
        "防御力": "def_percent",
        "攻击力": "atk_percent",
        "元素精通": "elemental_mastery",
        "暴击率": "crit_rate",
        "暴击伤害": "crit_damage",
        "治疗加成": "healing_bonus",
    },
}


def normalize_ocr_text(text: str) -> str:
    """Normalize harmless OCR typography without guessing semantic content."""

    normalized = unicodedata.normalize("NFKC", text).strip()
    normalized = normalized.replace("•", "").replace("·", "").replace("●", "")
    normalized = normalized.replace("：", ":").replace("﹢", "+")
    normalized = re.sub(r"\s+", "", normalized)
    for mistaken, corrected in _KNOWN_OCR_CORRECTIONS.items():
        normalized = normalized.replace(mistaken, corrected)
    return normalized


def _correction_warnings(tokens: list[OcrToken]) -> list[str]:
    warnings = []
    for token in tokens:
        compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", token.text))
        for mistaken, corrected in _KNOWN_OCR_CORRECTIONS.items():
            if mistaken in compact:
                warnings.append(f"已应用 OCR 固定纠正：{mistaken} → {corrected}")
    return warnings


def _with_joined_tokens(tokens: list[OcrToken]) -> list[OcrToken]:
    """Join an attribute label followed by a separate ``+value`` token."""

    result: list[OcrToken] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        text = normalize_ocr_text(current.text)
        if (
            text in _SUBSTAT_NAMES
            and index + 1 < len(tokens)
            and normalize_ocr_text(tokens[index + 1].text).startswith("+")
        ):
            following = tokens[index + 1]
            result.append(
                OcrToken(
                    text=text + normalize_ocr_text(following.text),
                    confidence=min(current.confidence, following.confidence),
                    bounding_box=current.bounding_box,
                )
            )
            index += 2
            continue
        result.append(current.model_copy(update={"text": text}))
        index += 1
    return result


def _find_position(tokens: list[OcrToken]) -> tuple[int, PositionId]:
    for index, token in enumerate(tokens):
        if token.text in _POSITION_BY_LABEL:
            return index, _POSITION_BY_LABEL[token.text]
    raise OcrParseError("未识别到圣遗物部位（生之花、死之羽、时之沙、空之杯或理之冠）")


def _find_level(tokens: list[OcrToken], start: int) -> tuple[int, int]:
    for index in range(start, len(tokens)):
        match = _LEVEL_PATTERN.fullmatch(tokens[index].text)
        if match:
            level = int(match.group(1))
            if 0 <= level <= 20:
                return index, level
    raise OcrParseError("未识别到 0–20 之间的圣遗物等级")


def _find_main_attribute(
    tokens: list[OcrToken], position: PositionId, start: int, stop: int
) -> tuple[str, OcrToken]:
    candidates = _MAIN_BY_POSITION[position]
    for token in tokens[start:stop]:
        for label, identifier in sorted(candidates.items(), key=lambda item: -len(item[0])):
            if token.text == label or token.text.startswith(label):
                return identifier, token
    expected = "、".join(candidates)
    raise OcrParseError(f"未识别到 {POSITION_LABELS_ZH[position]} 的主词条；可用值：{expected}")


def _substat_identifier(label: str, percentage: bool) -> AttributeId:
    if label == "生命值":
        return AttributeId.HP_PERCENT if percentage else AttributeId.FLAT_HP
    if label == "攻击力":
        return AttributeId.ATK_PERCENT if percentage else AttributeId.FLAT_ATK
    if label == "防御力":
        return AttributeId.DEF_PERCENT if percentage else AttributeId.FLAT_DEF
    return {
        "元素精通": AttributeId.ELEMENTAL_MASTERY,
        "元素充能效率": AttributeId.ENERGY_RECHARGE,
        "暴击率": AttributeId.CRIT_RATE,
        "暴击伤害": AttributeId.CRIT_DAMAGE,
    }[label]


def parse_ocr_tokens(
    tokens: list[OcrToken],
    *,
    confidence_threshold: float = 0.65,
    accept_low_confidence: bool = False,
) -> OcrParseResult:
    """Parse OCR tokens from one cropped Simplified-Chinese artifact card."""

    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence threshold must be between 0 and 1")
    if not tokens:
        raise OcrParseError("OCR 没有返回任何文字")
    normalized = _with_joined_tokens(tokens)
    position_index, position = _find_position(normalized)
    level_index, level = _find_level(normalized, position_index + 1)
    main_attribute, main_token = _find_main_attribute(
        normalized, position, position_index + 1, level_index
    )

    substats: dict[AttributeId, Decimal] = {}
    relevant = [normalized[position_index], main_token, normalized[level_index]]
    warnings = _correction_warnings(tokens)
    suspicious: list[str] = []
    for token in normalized[level_index + 1 :]:
        match = _SUBSTAT_PATTERN.fullmatch(token.text)
        if not match:
            if "+" in token.text and any(character.isdigit() for character in token.text):
                suspicious.append(token.text)
            continue
        label, raw_value, percent = match.groups()
        identifier = _substat_identifier(label, percent is not None)
        if identifier in substats:
            raise OcrParseError(f"副词条重复：{label}")
        try:
            value = Decimal(raw_value)
        except InvalidOperation as exc:
            raise OcrParseError(f"副词条数值无效：{token.text}") from exc
        substats[identifier] = value
        relevant.append(token)

    if suspicious:
        raise OcrParseError("疑似副词条但无法解析，请人工修正 OCR JSON：" + "、".join(suspicious))
    if len(substats) not in (3, 4):
        raise OcrParseError(f"应识别到 3 或 4 个副词条，实际识别到 {len(substats)} 个")
    if level >= 4 and len(substats) == 3:
        raise OcrParseError("+4 及以上五星圣遗物必须识别到 4 个副词条")

    low = [token for token in relevant if token.confidence < confidence_threshold]
    if low:
        summary = "、".join(f"{token.text}({token.confidence:.2f})" for token in low)
        if not accept_low_confidence:
            raise LowConfidenceError(
                f"OCR 置信度低于 {confidence_threshold:.2f}：{summary}；"
                "请人工修正 JSON 或显式允许低置信度"
            )
        warnings.append(f"已显式接受低置信度字段：{summary}")

    name = normalized[position_index - 1].text if position_index > 0 else None
    artifact = Artifact(
        position=position,
        main_attribute=main_attribute,
        level=level,
        rarity=5,
        substats=substats,
        name=name,
    )
    return OcrParseResult(artifact=artifact, relevant_tokens=relevant, warnings=warnings)


def parse_legacy_texts(texts: list[str]) -> Artifact:
    """Parse the historical ``list[str]`` EasyOCR output."""

    tokens = [OcrToken(text=text, confidence=1.0) for text in texts]
    return parse_ocr_tokens(tokens, confidence_threshold=0).artifact
