from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from .paths import config_path, models_dir, resolve_under_root, workspace_dir
from .storage.atomic import atomic_write_text


@dataclass(frozen=True)
class ModelConfig:
    backend: str = "gguf"
    path: str = ""
    context_size: int = 4096
    gpu_layers: int = 0
    temperature: float = 0.7
    max_tokens: int = 512

    @property
    def resolved_path(self) -> Path | None:
        if not self.path:
            return None
        resolved = resolve_under_root(self.path)
        models_root = models_dir().resolve()
        if models_root != resolved and models_root not in resolved.parents:
            raise ValueError("model path must be relative to models/")
        return resolved


@dataclass(frozen=True)
class WorkspaceConfig:
    root: str = "workspace"

    @property
    def resolved_root(self) -> Path:
        return resolve_under_root(self.root)


@dataclass(frozen=True)
class SafetyConfig:
    self_modify: bool = False
    sandbox: bool = True
    allow_outside_workspace: bool = False
    dry_run: bool = False
    max_file_bytes: int = 1_000_000
    max_search_matches: int = 200


@dataclass(frozen=True)
class HarnessConfig:
    model: ModelConfig
    workspace: WorkspaceConfig
    safety: SafetyConfig


def load_config(path: Path | None = None, dry_run: bool | None = None) -> HarnessConfig:
    cfg_path = path or config_path()
    raw: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as fh:
            raw = tomllib.load(fh)

    model = ModelConfig(**raw.get("model", {}))
    workspace = WorkspaceConfig(**raw.get("workspace", {}))
    safety = SafetyConfig(**raw.get("safety", {}))
    if dry_run is not None:
        safety = SafetyConfig(
            self_modify=safety.self_modify,
            sandbox=safety.sandbox,
            allow_outside_workspace=safety.allow_outside_workspace,
            dry_run=dry_run,
            max_file_bytes=safety.max_file_bytes,
            max_search_matches=safety.max_search_matches,
        )
    return HarnessConfig(model=model, workspace=workspace, safety=safety)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def dumps_config(config: HarnessConfig) -> str:
    lines = [
        "[model]",
        f"backend = {_toml_value(config.model.backend)}",
        f"path = {_toml_value(config.model.path)}",
        f"context_size = {_toml_value(config.model.context_size)}",
        f"gpu_layers = {_toml_value(config.model.gpu_layers)}",
        f"temperature = {_toml_value(config.model.temperature)}",
        f"max_tokens = {_toml_value(config.model.max_tokens)}",
        "",
        "[workspace]",
        f"root = {_toml_value(config.workspace.root)}",
        "",
        "[safety]",
        f"self_modify = {_toml_value(config.safety.self_modify)}",
        f"sandbox = {_toml_value(config.safety.sandbox)}",
        f"allow_outside_workspace = {_toml_value(config.safety.allow_outside_workspace)}",
        f"dry_run = {_toml_value(config.safety.dry_run)}",
        f"max_file_bytes = {_toml_value(config.safety.max_file_bytes)}",
        f"max_search_matches = {_toml_value(config.safety.max_search_matches)}",
        "",
    ]
    return "\n".join(lines)


def save_config(config: HarnessConfig, path: Path | None = None) -> None:
    atomic_write_text(path or config_path(), dumps_config(config))


def with_model_path(config: HarnessConfig, model_path: str) -> HarnessConfig:
    model = ModelConfig(
        backend=config.model.backend,
        path=model_path,
        context_size=config.model.context_size,
        gpu_layers=config.model.gpu_layers,
        temperature=config.model.temperature,
        max_tokens=config.model.max_tokens,
    )
    return HarnessConfig(model=model, workspace=config.workspace, safety=config.safety)
