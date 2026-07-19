from __future__ import annotations

from pathlib import Path

from harness.paths import _discover_root


def test_discover_root_from_release_executable_folder(tmp_path):
    root = tmp_path / "CrackStack"
    exe_dir = root / "releases" / "windows"
    exe_dir.mkdir(parents=True)
    (root / "config.toml").write_text("", encoding="utf-8")
    (root / "run.ps1").write_text("", encoding="utf-8")

    assert _discover_root(exe_dir) == root


def test_discover_root_falls_back_to_start(tmp_path):
    start = tmp_path / "isolated"
    start.mkdir()

    assert _discover_root(start) == start
