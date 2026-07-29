from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from yuanshen_score import cli
from yuanshen_score.batch import BatchEntry, BatchRequest
from yuanshen_score.errors import InputFormatError
from yuanshen_score.models import Artifact, OcrParseResult, OcrToken, ScoreRequest


def test_score_and_csv_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["score", "examples/artifact.v2.json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["scores"][0]["role"] == "夜兰"
    assert cli.main(["score", "examples/artifact.v2.json", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("role,current_score")


def test_score_file_protects_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "score.json"
    assert cli.main(["score", "examples/artifact.v2.json", "-o", str(output)]) == 0
    assert cli.main(["score", "examples/artifact.v2.json", "-o", str(output)]) == 2
    assert "--force" in capsys.readouterr().err
    assert (
        cli.main(
            [
                "score",
                "examples/artifact.v2.json",
                "-o",
                str(output),
                "--force",
                "--roles",
                "胡桃",
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["scores"][0]["role"] == "胡桃"


def test_simulate_and_plot_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plot = tmp_path / "plot.png"
    args = [
        "simulate",
        "examples/artifact.v2.json",
        "--runs",
        "3",
        "--seed",
        "7",
        "--target-level",
        "8",
        "--raw-samples",
        "--plot",
        str(plot),
    ]
    assert cli.main(args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["metadata"]["seed"] == 7
    assert len(output["results"][0]["raw_final_scores"]) == 3
    assert plot.is_file()
    assert cli.main(args) == 2
    assert "--force" in capsys.readouterr().err


def test_run_structured_and_legacy_image_input(
    tmp_path: Path,
    artifact: Artifact,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        cli.main(
            [
                "run",
                "examples/artifact.v2.json",
                "--runs",
                "1",
                "--seed",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    legacy = tmp_path / "legacy.json"
    legacy.write_text('{"item_path":"card.png","roles":["夜兰"],"runs":1}', encoding="utf-8")
    (tmp_path / "card.png").write_bytes(b"x")
    parsed = OcrParseResult(
        artifact=artifact,
        relevant_tokens=[OcrToken(text="时之沙", confidence=1)],
    )
    monkeypatch.setattr(cli, "_parse_image", lambda path, args, config: parsed)
    assert cli.main(["run", str(legacy), "--seed", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["metadata"]["seed"] == 2
    assert cli.main(["run", str(tmp_path / "card.png")]) == 2
    assert "--roles" in capsys.readouterr().err


def test_ocr_command_and_debug_tokens(
    tmp_path: Path,
    artifact: Artifact,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parsed = OcrParseResult(
        artifact=artifact,
        relevant_tokens=[OcrToken(text="时之沙", confidence=1)],
    )
    monkeypatch.setattr(cli, "_parse_image", lambda path, args, config: parsed)
    assert cli.main(["ocr", str(tmp_path / "card.png")]) == 0
    assert json.loads(capsys.readouterr().out)["artifact"]["position"] == "sands"


def test_batch_command_uses_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    artifact = json.loads(Path("examples/artifact.v2.json").read_text(encoding="utf-8"))["artifact"]
    manifest = tmp_path / "batch.json"
    manifest.write_text(
        json.dumps(
            {
                "roles": ["夜兰"],
                "runs": 1,
                "items": [{"id": "one", "artifact": artifact}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    assert cli.main(["batch", str(manifest), "--output-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


def test_models_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "install_easyocr_models",
        lambda path, languages: {"installed": str(path), "languages": languages},
    )
    monkeypatch.setattr(cli, "verify_easyocr_models", lambda path: {"verified": str(path)})
    assert (
        cli.main(
            [
                "models",
                "install",
                "easyocr-zh",
                "--model-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert "installed" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "models",
                "verify",
                "easyocr-zh",
                "--model-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert "verified" in capsys.readouterr().out


def test_cli_expected_unexpected_debug_and_interrupt_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "_execute", lambda args, config: (_ for _ in ()).throw(ValueError("bad"))
    )
    assert cli.main(["score", "x"]) == 2
    assert "error: bad" in capsys.readouterr().err

    monkeypatch.setattr(
        cli, "_execute", lambda args, config: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert cli.main(["score", "x"]) == 1
    assert "internal error" in capsys.readouterr().err

    monkeypatch.setattr(
        cli, "_execute", lambda args, config: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    assert cli.main(["score", "x"]) == 130
    assert "已取消" in capsys.readouterr().err


def test_helpers_cover_output_and_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = cli.load_config(cwd=tmp_path)
    args = SimpleNamespace(model_dir=None, device=None)
    engine = cli._engine(args, config)
    assert engine.model_dir == config.paths.model_dir
    with pytest.raises(InputFormatError):
        cli._request_for_run(tmp_path / "bad.json", SimpleNamespace(roles=None), config)


def test_rule_precedence_is_cli_then_input_then_config(
    tmp_path: Path, artifact: Artifact, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[paths]\nrules = "config-rules.json"\n', encoding="utf-8")
    config = cli.load_config(config_path)
    actual = cli.load_rule_set()
    selected: list[object] = []

    def record(source: object = None) -> object:
        selected.append(source)
        return actual

    monkeypatch.setattr(cli, "load_rule_set", record)
    implicit = ScoreRequest(artifact=artifact, roles=["夜兰"])
    assert "ruleset" not in implicit.model_fields_set
    cli._rule_set(SimpleNamespace(rules=None), config, implicit)
    assert selected[-1] == tmp_path / "config-rules.json"

    replaced = cli._replace_score_request(implicit, roles=["胡桃"])
    assert "ruleset" not in replaced.model_fields_set
    cli._rule_set(SimpleNamespace(rules=None), config, replaced)
    assert selected[-1] == tmp_path / "config-rules.json"

    explicit = ScoreRequest(
        artifact=artifact,
        roles=["夜兰"],
        ruleset="input-rules.json",
    )
    cli._rule_set(SimpleNamespace(rules=None), config, explicit)
    assert selected[-1] == "input-rules.json"

    cli._rule_set(SimpleNamespace(rules=Path("cli-rules.json")), config, explicit)
    assert selected[-1] == Path("cli-rules.json")

    batch = BatchRequest(
        roles=["夜兰"],
        items=[BatchEntry(id="one", artifact=artifact)],
    )
    replaced_batch = cli._replace_batch_request(batch, runs=3)
    assert "ruleset" not in replaced_batch.model_fields_set
    cli._rule_set(SimpleNamespace(rules=None), config, replaced_batch)
    assert selected[-1] == tmp_path / "config-rules.json"


def test_parser_version() -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
