"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from yuanshen_score import __version__
from yuanshen_score.batch import BatchRequest, load_batch_request, run_batch
from yuanshen_score.config import AppConfig, load_config
from yuanshen_score.errors import InputFormatError, OcrError, YuanshenScoreError
from yuanshen_score.io import (
    load_score_request,
    read_input_object,
    report_csv,
    write_output,
)
from yuanshen_score.models import OcrParseResult, ScoreRequest
from yuanshen_score.ocr import (
    EasyOcrEngine,
    install_easyocr_models,
    verify_easyocr_models,
)
from yuanshen_score.parser import parse_ocr_tokens
from yuanshen_score.plotting import render_plot
from yuanshen_score.rules import RuleSet, load_rule_set
from yuanshen_score.scoring import build_score_report
from yuanshen_score.serialization import content_sha256, pretty_json
from yuanshen_score.simulation import simulate


def _add_output_arguments(parser: argparse.ArgumentParser, *, csv: bool = True) -> None:
    parser.add_argument("-o", "--output", type=Path, help="输出文件；默认写入 stdout")
    if csv:
        parser.add_argument("--csv", action="store_true", help="输出 CSV 摘要")
    parser.add_argument("--force", action="store_true", help="显式覆盖已有输出")


def _add_ocr_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-dir", type=Path, help="EasyOCR 模型目录")
    parser.add_argument("--device", choices=("cpu", "cuda"), help="OCR 设备")
    parser.add_argument("--confidence", type=float, help="最低 OCR 置信度")
    parser.add_argument(
        "--accept-low-confidence",
        action="store_true",
        help="显式允许低置信度字段继续解析",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the public argparse tree."""

    parser = argparse.ArgumentParser(prog="yuanshen-score")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", type=Path, help="本地 TOML 配置文件")
    parser.add_argument("--debug", action="store_true", help="显示调试堆栈")
    commands = parser.add_subparsers(dest="command", required=True)

    score = commands.add_parser("score", help="对结构化圣遗物评分")
    score.add_argument("input", type=Path)
    score.add_argument("--roles", nargs="+", help="覆盖输入中的角色列表")
    score.add_argument("--rules", type=Path, help="自定义规则文件或旧规则目录")
    _add_output_arguments(score)

    simulate_parser = commands.add_parser("simulate", help="模拟强化分布")
    simulate_parser.add_argument("input", type=Path)
    simulate_parser.add_argument("--roles", nargs="+", help="覆盖输入中的角色列表")
    simulate_parser.add_argument("--rules", type=Path)
    simulate_parser.add_argument("--runs", type=int)
    simulate_parser.add_argument("--target-level", type=int)
    simulate_parser.add_argument("--seed", type=int)
    simulate_parser.add_argument("--raw-samples", action="store_true")
    simulate_parser.add_argument("--plot", type=Path, help="保存 PNG 图表")
    simulate_parser.add_argument("--show", action="store_true", help="显示交互图表")
    _add_output_arguments(simulate_parser)

    ocr_parser = commands.add_parser("ocr", help="截图转结构化 JSON")
    ocr_parser.add_argument("image", type=Path)
    _add_ocr_arguments(ocr_parser)
    ocr_parser.add_argument("--debug-ocr", type=Path, help="显式保存完整 OCR token 到本地文件")
    _add_output_arguments(ocr_parser, csv=False)

    run_parser = commands.add_parser("run", help="识别、评分、模拟和绘图的一键流程")
    run_parser.add_argument("input", type=Path, help="JSON 输入或已裁剪截图")
    run_parser.add_argument("--roles", nargs="+", help="截图输入时必需，或覆盖 JSON")
    run_parser.add_argument("--rules", type=Path)
    run_parser.add_argument("--runs", type=int)
    run_parser.add_argument("--target-level", type=int)
    run_parser.add_argument("--seed", type=int)
    run_parser.add_argument("--raw-samples", action="store_true")
    run_parser.add_argument("--plot", type=Path)
    run_parser.add_argument("--show", action="store_true")
    _add_ocr_arguments(run_parser)
    _add_output_arguments(run_parser)

    batch_parser = commands.add_parser("batch", help="运行或续跑批量任务")
    batch_parser.add_argument("manifest", type=Path)
    batch_parser.add_argument("--output-dir", type=Path)
    batch_parser.add_argument("--roles", nargs="+")
    batch_parser.add_argument("--rules", type=Path)
    batch_parser.add_argument("--runs", type=int)
    batch_parser.add_argument("--target-level", type=int)
    batch_parser.add_argument("--seed", type=int)
    batch_parser.add_argument("--resume", action="store_true")
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.add_argument("--raw-samples", action="store_true")
    _add_ocr_arguments(batch_parser)

    models = commands.add_parser("models", help="显式管理 OCR 模型")
    model_commands = models.add_subparsers(dest="model_command", required=True)
    install = model_commands.add_parser("install", help="下载并记录模型校验和")
    install.add_argument("model", choices=("easyocr-zh",))
    install.add_argument("--model-dir", type=Path)
    verify = model_commands.add_parser("verify", help="离线校验模型文件")
    verify.add_argument("model", choices=("easyocr-zh",))
    verify.add_argument("--model-dir", type=Path)
    return parser


def _rule_set(
    args: argparse.Namespace,
    config: AppConfig,
    request: ScoreRequest | BatchRequest | None = None,
) -> RuleSet:
    explicit = getattr(args, "rules", None)
    if explicit is not None:
        return load_rule_set(explicit)
    if request is not None and "ruleset" in request.model_fields_set:
        return load_rule_set(request.ruleset)
    if config.paths.rules is not None:
        return load_rule_set(config.paths.rules)
    return load_rule_set(request.ruleset if request is not None else None)


def _engine(args: argparse.Namespace, config: AppConfig) -> EasyOcrEngine:
    model_dir = getattr(args, "model_dir", None) or config.paths.model_dir
    device = getattr(args, "device", None) or config.ocr.device
    return EasyOcrEngine(model_dir, device=device, languages=config.ocr.languages)


def _parse_image(image: Path, args: argparse.Namespace, config: AppConfig) -> OcrParseResult:
    engine = _engine(args, config)
    tokens = engine.read(image)
    debug_output = getattr(args, "debug_ocr", None)
    if debug_output is not None:
        write_output(debug_output, {"tokens": tokens}, force=getattr(args, "force", False))
    threshold = (
        args.confidence if getattr(args, "confidence", None) is not None else config.ocr.confidence
    )
    return parse_ocr_tokens(
        tokens,
        confidence_threshold=threshold,
        accept_low_confidence=getattr(args, "accept_low_confidence", False),
    )


def _request_for_run(path: Path, args: argparse.Namespace, config: AppConfig) -> ScoreRequest:
    if path.suffix.lower() != ".json":
        if not args.roles:
            raise InputFormatError("直接输入截图时必须使用 --roles 指定至少一个角色")
        return ScoreRequest(artifact=_parse_image(path, args, config).artifact, roles=args.roles)

    raw = read_input_object(path)
    if "artifact" in raw or "item" in raw:
        request = load_score_request(path)
    elif "item_path" in raw:
        image = Path(raw["item_path"])
        if not image.is_absolute():
            image = path.resolve().parent / image
        roles = args.roles or raw.get("roles")
        if not roles:
            raise InputFormatError("OCR 输入必须提供角色列表")
        request_data: dict[str, Any] = {
            "artifact": _parse_image(image, args, config).artifact,
            "roles": roles,
        }
        for field in ("ruleset", "runs", "target_level", "seed"):
            if field in raw:
                request_data[field] = raw[field]
        request = ScoreRequest.model_validate(request_data)
    else:
        raise InputFormatError("JSON 必须包含 artifact、item 或 item_path")
    if args.roles:
        request = _replace_score_request(request, roles=args.roles)
    return request


def _simulation_options(
    request: ScoreRequest, args: argparse.Namespace, config: AppConfig
) -> tuple[int, int, int | None]:
    runs = args.runs if args.runs is not None else request.runs
    target = args.target_level if args.target_level is not None else request.target_level
    seed = args.seed if args.seed is not None else request.seed
    return (
        runs if runs is not None else config.simulation.runs,
        target if target is not None else config.simulation.target_level,
        seed,
    )


def _replace_score_request(request: ScoreRequest, **updates: Any) -> ScoreRequest:
    fields = {field: getattr(request, field) for field in request.model_fields_set}
    return ScoreRequest.model_validate({**fields, **updates})


def _replace_batch_request(request: BatchRequest, **updates: Any) -> BatchRequest:
    fields = {field: getattr(request, field) for field in request.model_fields_set}
    return BatchRequest.model_validate({**fields, **updates})


def _emit(value: Any, args: argparse.Namespace) -> None:
    output = getattr(args, "output", None)
    as_csv = getattr(args, "csv", False)
    if output is not None:
        write_output(output, value, force=getattr(args, "force", False), as_csv=as_csv)
    elif as_csv:
        sys.stdout.write(report_csv(value))
    else:
        sys.stdout.write(pretty_json(value))


def _plot_if_requested(report: Any, args: argparse.Namespace) -> None:
    output = getattr(args, "plot", None)
    show = getattr(args, "show", False)
    if output is None and not show:
        return
    if output is not None and output.exists() and not args.force:
        raise InputFormatError(f"图表文件已存在；如需覆盖请显式使用 --force：{output}")
    render_plot(report, output=output, show=show)


def _execute(args: argparse.Namespace, config: AppConfig) -> int:
    if args.command == "score":
        score_request = load_score_request(args.input)
        if args.roles:
            score_request = _replace_score_request(score_request, roles=args.roles)
        report = build_score_report(
            score_request.artifact,
            score_request.roles,
            _rule_set(args, config, score_request),
        )
        _emit(report, args)
        return 0

    if args.command in {"simulate", "run"}:
        simulation_request = (
            load_score_request(args.input)
            if args.command == "simulate"
            else _request_for_run(args.input, args, config)
        )
        if args.roles:
            simulation_request = _replace_score_request(simulation_request, roles=args.roles)
        runs, target, seed = _simulation_options(simulation_request, args, config)
        simulation_report = simulate(
            simulation_request.artifact,
            simulation_request.roles,
            _rule_set(args, config, simulation_request),
            runs=runs,
            target_level=target,
            seed=seed,
            include_raw=args.raw_samples,
        )
        _emit(simulation_report, args)
        _plot_if_requested(simulation_report, args)
        return 0

    if args.command == "ocr":
        _emit(_parse_image(args.image, args, config), args)
        return 0

    if args.command == "batch":
        batch_request = load_batch_request(args.manifest)
        updates = {
            key: value
            for key, value in {
                "roles": args.roles,
                "runs": args.runs,
                "target_level": args.target_level,
                "seed": args.seed,
            }.items()
            if value is not None
        }
        if updates:
            batch_request = _replace_batch_request(batch_request, **updates)
        output_dir = args.output_dir or config.paths.output_dir / (
            f"yuanshen-run-{content_sha256(batch_request)[:10]}"
        )
        needs_ocr = any(item.image is not None for item in batch_request.items)
        engine = _engine(args, config) if needs_ocr else None
        state = run_batch(
            batch_request,
            output_dir=output_dir,
            rule_set=_rule_set(args, config, batch_request),
            config=config,
            engine=engine,
            confidence=args.confidence,
            accept_low_confidence=args.accept_low_confidence,
            resume=args.resume,
            force=args.force,
            include_raw=args.raw_samples,
        )
        sys.stdout.write(pretty_json(state))
        return 1 if state["failed"] else 0

    if args.command == "models":
        model_dir = args.model_dir or config.paths.model_dir
        if args.model_command == "install":
            sys.stdout.write(
                pretty_json(install_easyocr_models(model_dir, languages=config.ocr.languages))
            )
        else:
            sys.stdout.write(pretty_json(verify_easyocr_models(model_dir)))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def _safe_error_message(error: Exception) -> str:
    message = str(error)
    replacements = {str(Path.home().resolve()): "<HOME>", str(Path.cwd().resolve()): "."}
    for source, replacement in replacements.items():
        message = message.replace(source, replacement)
    return message


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point returning a process status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        return _execute(args, config)
    except KeyboardInterrupt:
        print("error: 已取消", file=sys.stderr)
        return 130
    except (YuanshenScoreError, OcrError, ValidationError, ValueError, OSError) as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(f"error: {_safe_error_message(exc)}", file=sys.stderr)
        return 2
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        else:
            print(
                f"internal error: {type(exc).__name__}: {_safe_error_message(exc)}", file=sys.stderr
            )
        return 1
