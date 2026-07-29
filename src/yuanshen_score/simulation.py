"""Reproducible Monte Carlo artifact upgrades."""

from __future__ import annotations

import random
import secrets
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar

from yuanshen_score import __version__
from yuanshen_score.constants import RNG_ALGORITHM, AttributeId
from yuanshen_score.models import (
    Artifact,
    AttributeValue,
    DistributionSummary,
    RoleSimulation,
    SimulationMetadata,
    SimulationReport,
)
from yuanshen_score.rules import RuleSet
from yuanshen_score.scoring import score_artifact
from yuanshen_score.serialization import content_sha256

T = TypeVar("T")


class StableRandom:
    """Versioned sampling using only ``Random.random`` as its primitive."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._random = random.Random(seed)

    def pick(self, values: Sequence[T]) -> T:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        index = int(self._random.random() * len(values))
        return values[index]

    def weighted_pick(self, weights: Mapping[T, int]) -> T:
        candidates = sorted(
            ((candidate, weight) for candidate, weight in weights.items() if weight > 0),
            key=lambda pair: str(pair[0]),
        )
        if not candidates:
            raise ValueError("cannot choose when every weight is zero")
        total = sum(weight for _, weight in candidates)
        needle = self._random.random() * total
        cumulative = 0
        for candidate, weight in candidates:
            cumulative += weight
            if needle < cumulative:
                return candidate
        raise AssertionError("weighted sampling invariant failed")  # pragma: no cover


def _main_substat(main_attribute: str) -> AttributeId | None:
    try:
        return AttributeId(main_attribute)
    except ValueError:
        return None


def upgrade_once(artifact: Artifact, rule_set: RuleSet, rng: StableRandom) -> Artifact:
    """Apply one four-level upgrade roll and return a new artifact."""

    if artifact.level >= 20:
        raise ValueError("a level 20 artifact cannot be upgraded")
    substats = dict(artifact.substats)
    present = sorted(substats, key=lambda value: value.value)
    if len(present) == 3:
        excluded = set(present)
        main_substat = _main_substat(artifact.main_attribute)
        if main_substat is not None:
            excluded.add(main_substat)
        candidates = {
            attribute: weight
            for attribute, weight in rule_set.selection_weights.items()
            if attribute not in excluded
        }
        selected = rng.weighted_pick(candidates)
    elif len(present) == 4:
        selected = rng.pick(present)
    else:
        raise ValueError("an artifact must have three or four substats before upgrading")

    step = rng.pick(sorted(rule_set.upgrade_steps[selected]))
    substats[selected] = substats.get(selected, Decimal(0)) + step
    next_level = (artifact.level // 4 + 1) * 4
    return artifact.model_copy(update={"substats": substats, "level": next_level})


def upgrade_to_level(
    artifact: Artifact, target_level: int, rule_set: RuleSet, rng: StableRandom
) -> Artifact:
    """Upgrade to a target level while rolling only at four-level boundaries."""

    if target_level < artifact.level:
        raise ValueError("target level cannot be lower than the artifact level")
    if not 0 <= target_level <= 20:
        raise ValueError("target level must be between 0 and 20")
    result = artifact
    roll_count = target_level // 4 - artifact.level // 4
    for _ in range(roll_count):
        result = upgrade_once(result, rule_set, rng)
    return result.model_copy(update={"level": target_level})


def _quantile(sorted_values: Sequence[Decimal], numerator: int, denominator: int) -> Decimal:
    if not sorted_values:
        raise ValueError("cannot summarize an empty distribution")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = Decimal(len(sorted_values) - 1) * Decimal(numerator) / Decimal(denominator)
    lower = int(position)
    fraction = position - Decimal(lower)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def summarize(values: Sequence[Decimal]) -> DistributionSummary:
    """Summarize values with deterministic linear-interpolated quartiles."""

    if not values:
        raise ValueError("cannot summarize an empty distribution")
    ordered = sorted(values)
    return DistributionSummary(
        count=len(ordered),
        minimum=ordered[0],
        q1=_quantile(ordered, 1, 4),
        median=_quantile(ordered, 1, 2),
        mean=sum(ordered, Decimal(0)) / Decimal(len(ordered)),
        q3=_quantile(ordered, 3, 4),
        maximum=ordered[-1],
    )


def simulate(
    artifact: Artifact,
    roles: list[str],
    rule_set: RuleSet,
    *,
    runs: int = 10_000,
    target_level: int = 20,
    seed: int | None = None,
    include_raw: bool = False,
) -> SimulationReport:
    """Simulate upgrades and score every generated artifact for each role."""

    if runs < 1:
        raise ValueError("runs must be at least one")
    if runs > 1_000_000:
        raise ValueError("runs must not exceed 1,000,000")
    if not roles:
        raise ValueError("at least one role is required")
    if len(set(roles)) != len(roles):
        raise ValueError("roles must not contain duplicates")
    for role in roles:
        if role not in rule_set.role_weights:
            rule_set.role_weight_for(role, next(iter(artifact.substats)))
    if target_level < artifact.level or target_level > 20:
        raise ValueError("target level must be between the artifact level and 20")

    effective_seed = secrets.randbits(64) if seed is None else seed
    if not 0 <= effective_seed <= 18_446_744_073_709_551_615:
        raise ValueError("seed must be an unsigned 64-bit integer")
    rng = StableRandom(effective_seed)
    current = {role: score_artifact(artifact, role, rule_set) for role in roles}
    final_scores: dict[str, list[Decimal]] = {role: [] for role in roles}

    for _ in range(runs):
        upgraded = upgrade_to_level(artifact, target_level, rule_set, rng)
        for role in roles:
            final_scores[role].append(score_artifact(upgraded, role, rule_set))

    results = []
    for role in roles:
        final = final_scores[role]
        gains = [value - current[role] for value in final]
        results.append(
            RoleSimulation(
                role=role,
                current_score=current[role],
                final_score=summarize(final),
                score_gain=summarize(gains),
                raw_final_scores=final if include_raw else None,
            )
        )

    payload = {
        "artifact": artifact,
        "roles": roles,
        "ruleset": rule_set.id,
        "runs": runs,
        "target_level": target_level,
    }
    return SimulationReport(
        metadata=SimulationMetadata(
            application_version=__version__,
            ruleset=rule_set.id,
            input_sha256=content_sha256(payload),
            generated_at=datetime.now(UTC),
            seed=effective_seed,
            rng_algorithm=RNG_ALGORITHM,
            runs=runs,
            target_level=target_level,
        ),
        artifact=artifact,
        substat_details=[
            AttributeValue.from_pair(identifier, value)
            for identifier, value in sorted(
                artifact.substats.items(), key=lambda pair: pair[0].value
            )
        ],
        results=results,
    )
