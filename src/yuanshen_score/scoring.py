"""Pure artifact scoring."""

from __future__ import annotations

from decimal import Decimal

from yuanshen_score import __version__
from yuanshen_score.models import (
    Artifact,
    AttributeValue,
    RoleScore,
    ScoreMetadata,
    ScoreReport,
)
from yuanshen_score.rules import RuleSet
from yuanshen_score.serialization import content_sha256


def score_artifact(artifact: Artifact, role: str, rule_set: RuleSet) -> Decimal:
    """Score an artifact for one role without mutating any input."""

    total = Decimal(0)
    for attribute, value in artifact.substats.items():
        total += (
            value
            * rule_set.attribute_weights[attribute]
            * rule_set.role_weight_for(role, attribute)
        )
    return total / Decimal(100)


def build_score_report(artifact: Artifact, roles: list[str], rule_set: RuleSet) -> ScoreReport:
    """Build a deterministic score report."""

    scores = [
        RoleScore(role=role, score=score_artifact(artifact, role, rule_set)) for role in roles
    ]
    payload = {"artifact": artifact, "roles": roles, "ruleset": rule_set.id}
    return ScoreReport(
        metadata=ScoreMetadata(
            application_version=__version__,
            ruleset=rule_set.id,
            input_sha256=content_sha256(payload),
        ),
        artifact=artifact,
        substat_details=[
            AttributeValue.from_pair(identifier, value)
            for identifier, value in sorted(
                artifact.substats.items(), key=lambda pair: pair[0].value
            )
        ],
        scores=scores,
    )
