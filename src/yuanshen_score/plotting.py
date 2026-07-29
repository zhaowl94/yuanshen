"""Optional Matplotlib rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yuanshen_score.errors import YuanshenScoreError
from yuanshen_score.models import SimulationReport


def _matplotlib(*, headless: bool = False) -> tuple[Any, Any]:
    try:
        import matplotlib

        if headless:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as pyplot
    except ImportError as exc:
        raise YuanshenScoreError(
            "绘图依赖未安装；请安装 yuanshen-score[plot] 或 yuanshen-score[all]"
        ) from exc
    return matplotlib, pyplot


def create_figure(report: SimulationReport, *, headless: bool = False) -> Any:
    """Create a summary box plot without requiring raw samples."""

    matplotlib, pyplot = _matplotlib(headless=headless)
    matplotlib.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False
    figure, axes = pyplot.subplots(figsize=(max(7, len(report.results) * 1.2), 5))
    boxes = []
    for result in report.results:
        summary = result.final_score
        boxes.append(
            {
                "label": result.role,
                "whislo": float(summary.minimum),
                "q1": float(summary.q1),
                "med": float(summary.median),
                "mean": float(summary.mean),
                "q3": float(summary.q3),
                "whishi": float(summary.maximum),
                "fliers": [],
            }
        )
    axes.bxp(boxes, showmeans=True)
    axes.scatter(
        range(1, len(report.results) + 1),
        [float(result.current_score) for result in report.results],
        marker="D",
        color="#C23B22",
        label="当前分数",
        zorder=3,
    )
    axes.set_title(
        f"强化至 +{report.metadata.target_level} 的分数分布"
        f"（n={report.metadata.runs}, seed={report.metadata.seed}）"
    )
    axes.set_ylabel("分数")
    axes.grid(axis="y", alpha=0.25)
    axes.legend()
    figure.tight_layout()
    return figure


def render_plot(
    report: SimulationReport,
    *,
    output: Path | None = None,
    show: bool = False,
) -> Any:
    """Save and/or display a report plot, returning the Figure."""

    _, pyplot = _matplotlib(headless=not show)
    figure = create_figure(report, headless=not show)
    if output is not None:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=160, metadata={"Software": "yuanshen-score"})
    if show:
        pyplot.show()
    return figure
