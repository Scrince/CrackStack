from __future__ import annotations

from pathlib import Path
import difflib
import re

from harness.config import HarnessConfig
from harness.paths import harness_root, plugins_dir
from harness.sandbox import analyze_tool_source, smoke_test_module
from harness.storage.audit import log_audit
from harness.storage.atomic import atomic_write_text
from harness.storage.history import SelfModificationHistory
from harness.tools.filesystem import _apply_simple_unified_diff
from harness.tools.plugin_loader import load_tool_module
from harness.tools.registry import ToolRegistry


SAFE_MODULE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _safe_module_path(module_name: str) -> Path:
    if not SAFE_MODULE_RE.fullmatch(module_name):
        raise ValueError("module_name must be a valid Python identifier")
    directory = plugins_dir() / "generated_tools"
    return directory / f"{module_name}.py"


def _unified_patch(path: Path, old: str, new: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=path.name,
            tofile=path.name,
        )
    )


def _apply_text_patch(path: Path, patch: str) -> str:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    return _apply_simple_unified_diff(original, patch)


class SelfModifyTools:
    def __init__(self, config: HarnessConfig, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self.history = SelfModificationHistory()

    def install_tool_module(
        self,
        module_name: str,
        source: str,
        confirm_core_edit: bool = False,
    ) -> str:
        if not self.config.safety.self_modify:
            raise PermissionError("self-modification is disabled in config.toml")
        if not self.config.safety.sandbox:
            raise PermissionError(
                "installing generated tools requires safety.sandbox=true "
                "(static analysis + isolated smoke test)"
            )

        static_issues = analyze_tool_source(source)
        if static_issues:
            raise RuntimeError(
                "sandbox rejected tool module (static analysis):\n" + "\n".join(static_issues)
            )

        target = _safe_module_path(module_name)
        plugins_root = plugins_dir().resolve()
        resolved = target.resolve()
        if plugins_root != resolved and plugins_root not in resolved.parents:
            if not confirm_core_edit:
                raise PermissionError("core/outside-plugin edits require confirm_core_edit=true")

        target.parent.mkdir(parents=True, exist_ok=True)
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        patch = _unified_patch(target, original, source)
        if not patch:
            return f"no changes for {target.relative_to(harness_root()).as_posix()}"
        if self.config.safety.dry_run:
            return f"dry-run: would install {target.relative_to(harness_root()).as_posix()}\n{patch}"

        before = self.history.snapshot(f"pre self-edit {module_name}")
        updated = _apply_text_patch(target, patch)
        atomic_write_text(target, updated)
        log_audit("self_modify_patch", target, {"module": module_name})

        sandbox = smoke_test_module(target)
        if not sandbox.ok:
            if original:
                atomic_write_text(target, original)
            else:
                target.unlink(missing_ok=True)
            self.history.snapshot(f"rollback failed self-edit {module_name}")
            raise RuntimeError(f"sandbox rejected tool module:\n{sandbox.stderr or sandbox.stdout}")

        load_tool_module(target, self.registry)
        after = self.history.snapshot(f"post self-edit {module_name}")
        before_rev = before.revision or "none"
        after_rev = after.revision or "none"
        return (
            f"installed {target.relative_to(harness_root()).as_posix()} "
            f"(before={before_rev}, after={after_rev})"
        )


def register_self_modify_tools(registry: ToolRegistry, config: HarnessConfig) -> None:
    tools = SelfModifyTools(config, registry)
    registry.register(
        "install_tool_module",
        "Install or update a generated Python tool module under plugins/generated_tools after sandbox smoke testing.",
        {
            "type": "object",
            "properties": {
                "module_name": {"type": "string"},
                "source": {"type": "string"},
                "confirm_core_edit": {"type": "boolean", "default": False},
            },
            "required": ["module_name", "source"],
        },
        tools.install_tool_module,
    )
