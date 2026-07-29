from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from yuanshen_score.constants import AttributeId
from yuanshen_score.models import Artifact
from yuanshen_score.rules import RuleSet
from yuanshen_score.serialization import json_ready
from yuanshen_score.simulation import (
    StableRandom,
    _main_substat,
    _quantile,
    simulate,
    summarize,
    upgrade_once,
    upgrade_to_level,
)


def test_stable_random_is_repeatable_and_validates_empty() -> None:
    left = StableRandom(42)
    right = StableRandom(42)
    assert [left.pick([1, 2, 3]) for _ in range(10)] == [right.pick([1, 2, 3]) for _ in range(10)]
    with pytest.raises(ValueError, match="empty"):
        left.pick([])
    with pytest.raises(ValueError, match="every weight"):
        left.weighted_pick({"x": 0})


def test_three_stat_upgrade_adds_allowed_fourth_without_mutation(
    three_stat_artifact: Artifact, rule_set: RuleSet
) -> None:
    before = three_stat_artifact.model_copy(deep=True)
    result = upgrade_once(three_stat_artifact, rule_set, StableRandom(7))
    assert three_stat_artifact == before
    assert len(result.substats) == 4
    assert AttributeId.ATK_PERCENT not in result.substats
    assert result.level == 4


def test_three_stat_damage_main_does_not_exclude_a_substat(
    three_stat_artifact: Artifact, rule_set: RuleSet
) -> None:
    goblet = three_stat_artifact.model_copy(update={"main_attribute": "pyro_damage_bonus"})
    assert _main_substat(goblet.main_attribute) is None
    assert len(upgrade_once(goblet, rule_set, StableRandom(3)).substats) == 4


def test_four_stat_upgrade_only_changes_existing_attribute(
    artifact: Artifact, rule_set: RuleSet
) -> None:
    result = upgrade_once(artifact, rule_set, StableRandom(1))
    assert set(result.substats) == set(artifact.substats)
    changed = [key for key in artifact.substats if artifact.substats[key] != result.substats[key]]
    assert len(changed) == 1
    assert result.level == 8


def test_upgrade_target_boundaries(artifact: Artifact, rule_set: RuleSet) -> None:
    unchanged = upgrade_to_level(artifact, 7, rule_set, StableRandom(1))
    assert unchanged.substats == artifact.substats
    assert unchanged.level == 7
    rolled = upgrade_to_level(artifact, 8, rule_set, StableRandom(1))
    assert rolled.substats != artifact.substats
    with pytest.raises(ValueError, match="lower"):
        upgrade_to_level(artifact, 5, rule_set, StableRandom(1))
    with pytest.raises(ValueError, match="between"):
        upgrade_to_level(artifact, 21, rule_set, StableRandom(1))


def test_upgrade_once_rejects_complete_or_malformed(artifact: Artifact, rule_set: RuleSet) -> None:
    with pytest.raises(ValueError, match="level 20"):
        upgrade_once(artifact.model_copy(update={"level": 20}), rule_set, StableRandom(1))
    object.__setattr__(artifact, "substats", {AttributeId.CRIT_RATE: Decimal("3.9")})
    with pytest.raises(ValueError, match="three or four"):
        upgrade_once(artifact, rule_set, StableRandom(1))


def test_summary_uses_linear_quartiles() -> None:
    summary = summarize([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")])
    assert summary.q1 == Decimal("1.75")
    assert summary.median == Decimal("2.5")
    assert summary.q3 == Decimal("3.25")
    assert summary.mean == Decimal("2.5")
    assert summarize([Decimal("7")]).median == Decimal("7")
    with pytest.raises(ValueError, match="empty"):
        summarize([])
    with pytest.raises(ValueError, match="empty"):
        _quantile([], 1, 2)


def test_simulation_same_seed_same_results(artifact: Artifact, rule_set: RuleSet) -> None:
    first = simulate(artifact, ["夜兰", "胡桃"], rule_set, runs=50, seed=123)
    second = simulate(artifact, ["夜兰", "胡桃"], rule_set, runs=50, seed=123)
    assert first.results == second.results
    assert first.metadata.seed == second.metadata.seed == 123
    assert first.metadata.input_sha256 == second.metadata.input_sha256


def test_simulation_raw_samples_and_generated_seed(
    monkeypatch: pytest.MonkeyPatch, artifact: Artifact, rule_set: RuleSet
) -> None:
    monkeypatch.setattr("yuanshen_score.simulation.secrets.randbits", lambda bits: 99)
    report = simulate(artifact, ["夜兰"], rule_set, runs=3, seed=None, include_raw=True)
    assert report.metadata.seed == 99
    assert report.results[0].raw_final_scores is not None
    assert len(report.results[0].raw_final_scores or []) == 3
    assert json_ready(report)["metadata"]["rng_algorithm"] == "python-mt19937-v1"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"runs": 0}, "at least one"),
        ({"runs": 1_000_001}, "exceed"),
        ({"roles": []}, "at least one role"),
        ({"roles": ["夜兰", "夜兰"]}, "duplicates"),
        ({"roles": ["不存在"]}, "unknown role"),
        ({"target_level": 5}, "between"),
        ({"seed": -1}, "unsigned"),
    ],
)
def test_simulation_rejects_invalid_options(
    artifact: Artifact, rule_set: RuleSet, kwargs: dict[str, object], message: str
) -> None:
    options = {"roles": ["夜兰"], "runs": 1, "target_level": 20, "seed": 1}
    options.update(kwargs)
    with pytest.raises(ValueError, match=message):
        simulate(artifact, rule_set=rule_set, **options)  # type: ignore[arg-type]


@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_upgrade_is_pure_for_arbitrary_seed(
    seed: int, artifact: Artifact, rule_set: RuleSet
) -> None:
    before = artifact.model_dump()
    upgrade_to_level(artifact, 20, rule_set, StableRandom(seed))
    assert artifact.model_dump() == before
