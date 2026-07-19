from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from harness.sandbox import analyze_tool_source
from harness.tools.registry import ToolRegistry

LOGGER = logging.getLogger(__name__)


def load_tool_module(module_path: Path, registry: ToolRegistry) -> None:
    try:
        source = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"could not read tool module: {module_path}: {exc}") from exc

    issues = analyze_tool_source(source)
    if issues:
        raise RuntimeError(
            f"tool module failed sandbox static analysis: {module_path}: "
            + "; ".join(issues)
        )

    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module spec: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    register = getattr(module, "register", None)
    if register is None:
        raise RuntimeError("tool module must define register(registry)")
    register(registry)


def load_generated_tools(
    directory: Path,
    registry: ToolRegistry,
    *,
    sandbox: bool = True,
) -> list[str]:
    """
    Load generated tool modules.

    When sandbox is False, generated tools are not loaded (operators must not
    execute unreviewed plugin code without the analysis gate).
    """
    loaded: list[str] = []
    if not sandbox:
        LOGGER.warning(
            "safety.sandbox is false: skipping generated tool load from %s",
            directory,
        )
        return loaded
    if not directory.exists():
        return loaded
    for module_path in sorted(directory.glob("*.py")):
        try:
            load_tool_module(module_path, registry)
        except Exception:
            LOGGER.exception("failed to load generated tool module: %s", module_path)
            continue
        loaded.append(module_path.name)
    return loaded
