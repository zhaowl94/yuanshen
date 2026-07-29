"""Stable identifiers and legacy mappings."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal


class AttributeId(StrEnum):
    """Stable identifiers for artifact substats."""

    FLAT_HP = "flat_hp"
    FLAT_ATK = "flat_atk"
    FLAT_DEF = "flat_def"
    ELEMENTAL_MASTERY = "elemental_mastery"
    ENERGY_RECHARGE = "energy_recharge"
    HP_PERCENT = "hp_percent"
    ATK_PERCENT = "atk_percent"
    DEF_PERCENT = "def_percent"
    CRIT_RATE = "crit_rate"
    CRIT_DAMAGE = "crit_damage"


class PositionId(StrEnum):
    """Stable artifact slot identifiers."""

    FLOWER = "flower"
    PLUME = "plume"
    SANDS = "sands"
    GOBLET = "goblet"
    CIRCLET = "circlet"


class RoleStatId(StrEnum):
    """Stable identifiers used by the legacy role preference table."""

    HP = "hp"
    ATK = "atk"
    DEF = "def"
    ELEMENTAL_MASTERY = "elemental_mastery"
    ENERGY_RECHARGE = "energy_recharge"
    CRIT_RATE = "crit_rate"
    CRIT_DAMAGE = "crit_damage"


ATTRIBUTE_LABELS_ZH: dict[AttributeId, str] = {
    AttributeId.FLAT_HP: "小生命",
    AttributeId.FLAT_ATK: "小攻击",
    AttributeId.FLAT_DEF: "小防御",
    AttributeId.ELEMENTAL_MASTERY: "精通",
    AttributeId.ENERGY_RECHARGE: "充能",
    AttributeId.HP_PERCENT: "大生命",
    AttributeId.ATK_PERCENT: "大攻击",
    AttributeId.DEF_PERCENT: "大防御",
    AttributeId.CRIT_RATE: "暴击",
    AttributeId.CRIT_DAMAGE: "爆伤",
}
LEGACY_ATTRIBUTE_IDS = {label: identifier for identifier, label in ATTRIBUTE_LABELS_ZH.items()}

ATTRIBUTE_UNITS: dict[AttributeId, str] = {
    AttributeId.FLAT_HP: "flat",
    AttributeId.FLAT_ATK: "flat",
    AttributeId.FLAT_DEF: "flat",
    AttributeId.ELEMENTAL_MASTERY: "flat",
    AttributeId.ENERGY_RECHARGE: "percentage_point",
    AttributeId.HP_PERCENT: "percentage_point",
    AttributeId.ATK_PERCENT: "percentage_point",
    AttributeId.DEF_PERCENT: "percentage_point",
    AttributeId.CRIT_RATE: "percentage_point",
    AttributeId.CRIT_DAMAGE: "percentage_point",
}

ATTRIBUTE_ROLE_STAT: dict[AttributeId, RoleStatId] = {
    AttributeId.FLAT_HP: RoleStatId.HP,
    AttributeId.HP_PERCENT: RoleStatId.HP,
    AttributeId.FLAT_ATK: RoleStatId.ATK,
    AttributeId.ATK_PERCENT: RoleStatId.ATK,
    AttributeId.FLAT_DEF: RoleStatId.DEF,
    AttributeId.DEF_PERCENT: RoleStatId.DEF,
    AttributeId.ELEMENTAL_MASTERY: RoleStatId.ELEMENTAL_MASTERY,
    AttributeId.ENERGY_RECHARGE: RoleStatId.ENERGY_RECHARGE,
    AttributeId.CRIT_RATE: RoleStatId.CRIT_RATE,
    AttributeId.CRIT_DAMAGE: RoleStatId.CRIT_DAMAGE,
}

ROLE_STAT_LABELS_ZH: dict[RoleStatId, str] = {
    RoleStatId.HP: "生命",
    RoleStatId.ATK: "攻击",
    RoleStatId.DEF: "防御",
    RoleStatId.ELEMENTAL_MASTERY: "精通",
    RoleStatId.ENERGY_RECHARGE: "充能",
    RoleStatId.CRIT_RATE: "暴击",
    RoleStatId.CRIT_DAMAGE: "爆伤",
}
LEGACY_ROLE_STAT_IDS = {label: identifier for identifier, label in ROLE_STAT_LABELS_ZH.items()}

POSITION_LABELS_ZH: dict[PositionId, str] = {
    PositionId.FLOWER: "生之花",
    PositionId.PLUME: "死之羽",
    PositionId.SANDS: "时之沙",
    PositionId.GOBLET: "空之杯",
    PositionId.CIRCLET: "理之冠",
}
LEGACY_POSITION_IDS = {
    1: PositionId.FLOWER,
    2: PositionId.PLUME,
    3: PositionId.SANDS,
    4: PositionId.GOBLET,
    5: PositionId.CIRCLET,
}
POSITION_NUMBER = {position: number for number, position in LEGACY_POSITION_IDS.items()}

# Main stats share substat identifiers when possible. Damage and healing bonuses are
# intentionally represented by stable strings because they never participate in v1 scoring.
MAIN_ATTRIBUTE_LABELS_ZH: dict[str, str] = {
    "flat_hp": "生命值",
    "flat_atk": "攻击力",
    "hp_percent": "生命值",
    "atk_percent": "攻击力",
    "def_percent": "防御力",
    "elemental_mastery": "元素精通",
    "energy_recharge": "元素充能效率",
    "crit_rate": "暴击率",
    "crit_damage": "暴击伤害",
    "healing_bonus": "治疗加成",
    "physical_damage_bonus": "物理伤害加成",
    "pyro_damage_bonus": "火元素伤害加成",
    "hydro_damage_bonus": "水元素伤害加成",
    "dendro_damage_bonus": "草元素伤害加成",
    "electro_damage_bonus": "雷元素伤害加成",
    "anemo_damage_bonus": "风元素伤害加成",
    "cryo_damage_bonus": "冰元素伤害加成",
    "geo_damage_bonus": "岩元素伤害加成",
}

LEGACY_MAIN_ATTRIBUTE_IDS: dict[str, str] = {
    "小生命": "flat_hp",
    "小攻击": "flat_atk",
    "大生命": "hp_percent",
    "大攻击": "atk_percent",
    "大防御": "def_percent",
    "精通": "elemental_mastery",
    "充能": "energy_recharge",
    "暴击": "crit_rate",
    "爆伤": "crit_damage",
    "治疗": "healing_bonus",
    "物伤": "physical_damage_bonus",
    "火伤": "pyro_damage_bonus",
    "水伤": "hydro_damage_bonus",
    "草伤": "dendro_damage_bonus",
    "雷伤": "electro_damage_bonus",
    "风伤": "anemo_damage_bonus",
    "冰伤": "cryo_damage_bonus",
    "岩伤": "geo_damage_bonus",
}
MAIN_ATTRIBUTE_LEGACY = {
    identifier: label for label, identifier in LEGACY_MAIN_ATTRIBUTE_IDS.items()
}

SCHEMA_VERSION: Final[Literal["2.0"]] = "2.0"
RULE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"
RNG_ALGORITHM: Final[Literal["python-mt19937-v1"]] = "python-mt19937-v1"
