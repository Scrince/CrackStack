from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT_ENV_VAR = "CRACKSTACK_ROOT"


def harness_root() -> Path:
    
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return _discover_root(Path(sys.executable).resolve().parent)
    return Path(__file__).resolve().parents[1]


def _discover_root(start: Path) -> Path:
    
    for candidate in (start, *start.parents):
        if (candidate / "config.toml").exists() and (
            (candidate / "run.ps1").exists() or (candidate / "run.sh").exists()
        ):
            return candidate
    return start


def root_path(*parts: str) -> Path:
    return harness_root().joinpath(*parts)


def config_path() -> Path:
    return root_path("config.toml")


def models_dir() -> Path:
    return root_path("models")


def workspace_dir() -> Path:
    return root_path("workspace")


def logs_dir() -> Path:
    return root_path("logs")


def state_dir() -> Path:
    return root_path("state")


def runtime_dir() -> Path:
    return root_path("runtime")


def plugins_dir() -> Path:
    return root_path("plugins")


def generated_dir() -> Path:
    return root_path("generated")


def ensure_base_dirs() -> None:
    for path in (
        models_dir(),
        workspace_dir(),
        logs_dir(),
        state_dir(),
        plugins_dir(),
        generated_dir(),
        runtime_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)


def resolve_under_root(relative_path: str | Path) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"absolute paths are not portable: {path}")
    return root_path(*path.parts).resolve()
