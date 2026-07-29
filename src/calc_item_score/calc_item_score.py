"""Installed aliases for the historical module-level functions."""

from yuanshen_score.compat import (
    calc_score,
    calc_score_roles,
    check_valid,
    legacy_main,
    load_attrs_choice,
    load_attrs_step,
    load_attrs_weight,
    load_input_param,
    load_roles_weight,
    ocr_item,
    parse_result,
    trans_role_weight,
    upgrade,
    upgrade_once,
)

__all__ = [
    "calc_score",
    "calc_score_roles",
    "check_valid",
    "load_attrs_choice",
    "load_attrs_step",
    "load_attrs_weight",
    "load_input_param",
    "load_roles_weight",
    "ocr_item",
    "parse_result",
    "trans_role_weight",
    "upgrade",
    "upgrade_once",
]


if __name__ == "__main__":
    raise SystemExit(legacy_main())
