from __future__ import annotations

from pathlib import Path

import pytest

from yuanshen_score.errors import YuanshenScoreError
from yuanshen_score.models import Artifact
from yuanshen_score.plotting import _matplotlib, create_figure, render_plot
from yuanshen_score.rules import RuleSet
from yuanshen_score.simulation import simulate


def test_plot_can_render_headlessly(tmp_path: Path, artifact: Artifact, rule_set: RuleSet) -> None:
    report = simulate(artifact, ["夜兰", "胡桃"], rule_set, runs=10, seed=1)
    figure = create_figure(report)
    assert len(figure.axes) == 1
    output = tmp_path / "plot.png"
    assert render_plot(report, output=output, show=False) is not None
    assert output.read_bytes().startswith(b"\x89PNG")


def test_plot_dependency_error_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    original = __import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("matplotlib"):
            raise ImportError("blocked")
        return original(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(YuanshenScoreError, match=r"\[plot\]"):
        _matplotlib()
