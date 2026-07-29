#!/usr/bin/env python
"""Backward-compatible wrapper for the historical single-file program."""

from __future__ import annotations

import sys
from pathlib import Path

_SOURCE = Path(__file__).resolve().parents[1] / "src"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))

from yuanshen_score.compat import (  # noqa: E402,F401
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

if __name__ == "__main__":
    raise SystemExit(legacy_main())
