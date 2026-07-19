from __future__ import annotations

from harness.cli import _build_parser
from harness.cli import run_once


def test_dry_run_before_subcommand():
    args = _build_parser().parse_args(["--dry-run", "run", "do", "thing"])
    assert args.dry_run is True
    assert args.command == "run"


def test_dry_run_after_subcommand():
    args = _build_parser().parse_args(["run", "--dry-run", "do", "thing"])
    assert args.dry_run is True
    assert args.command == "run"


def test_tools_subcommands_parse():
    args = _build_parser().parse_args(["tools", "specs"])
    assert args.command == "tools"
    assert args.tools_command == "specs"


def test_gui_command_parses():
    args = _build_parser().parse_args(["gui"])
    assert args.command == "gui"


def test_run_once_reports_missing_model_without_traceback(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))

    status = run_once("hello")

    assert status == 1
