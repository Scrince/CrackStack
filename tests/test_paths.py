from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_harness_root_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    import harness.paths as paths

    assert paths.harness_root() == tmp_path.resolve()
    assert paths.models_dir() == tmp_path.resolve() / "models"


def test_no_absolute_path_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    import harness.paths as paths

    importlib.reload(paths)
    try:
        paths.resolve_under_root(Path.cwd())
    except ValueError as exc:
        assert "absolute paths" in str(exc)
    else:
        raise AssertionError("absolute paths should be rejected")


def test_copy_to_new_root_still_discovers_files(tmp_path):
    source = Path.cwd()
    target = tmp_path / "MovedHarness"
    ignore = shutil.ignore_patterns(
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".tmp",
        "generated",
        "logs",
        "models",
        "releases",
        "runtime",
        "state",
    )
    shutil.copytree(source, target, ignore=ignore)

    model_dir = target / "models"
    model_dir.mkdir(exist_ok=True)
    (model_dir / "tiny.gguf").write_bytes(b"stub")

    env = os.environ.copy()
    env["CRACKSTACK_ROOT"] = str(target)
    env["PYTHONPATH"] = str(target)
    result = subprocess.run(
        [sys.executable, "-m", "harness.cli", "models"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "tiny.gguf" in result.stdout
