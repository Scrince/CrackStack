from __future__ import annotations

import ast
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

from harness.paths import harness_root


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    stdout: str
    stderr: str


# Generated tool modules must not reach OS/process/network APIs directly.
# Workspace I/O belongs to harness filesystem tools, not plugin code.
_FORBIDDEN_MODULES = frozenset(
    {
        "os",
        "subprocess",
        "socket",
        "ctypes",
        "importlib",
        "multiprocessing",
        "pathlib",
        "shutil",
        "signal",
        "sys",
        "builtins",
        "pty",
        "fcntl",
        "resource",
        "tempfile",
        "http",
        "urllib",
        "requests",
        "aiohttp",
        "pickle",
        "marshal",
        "code",
        "codeop",
        "pty",
        "webbrowser",
    }
)

_FORBIDDEN_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "input",
        "help",
        "exit",
        "quit",
        "memoryview",
    }
)


def analyze_tool_source(source: str) -> list[str]:
    """Return human-readable issues if source is unsafe for sandbox install."""
    issues: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} (line {exc.lineno})"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _FORBIDDEN_MODULES:
                    issues.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".", 1)[0]
                if root in _FORBIDDEN_MODULES:
                    issues.append(f"forbidden import: {node.module}")
            if node.level and node.level > 0:
                issues.append("relative imports are not allowed in generated tools")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_NAMES:
                issues.append(f"forbidden call: {func.id}()")
            elif isinstance(func, ast.Attribute) and func.attr in {"system", "popen", "spawn"}:
                issues.append(f"forbidden call: .{func.attr}()")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in _FORBIDDEN_NAMES:
                issues.append(f"forbidden name: {node.id}")
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                if node.attr in {"__import__", "__builtins__", "__loader__", "__spec__"}:
                    issues.append(f"forbidden attribute: {node.attr}")
    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _restricted_env(root: Path) -> dict[str, str]:
    """Build a minimal environment for the smoke-test subprocess."""
    env: dict[str, str] = {
        "CRACKSTACK_ROOT": str(root),
        "PYTHONPATH": str(root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONSAFEPATH": "1",
    }
    # Preserve only what the interpreter needs to start.
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "SystemRoot", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def smoke_test_module(module_path: Path, timeout_seconds: int = 10) -> SandboxResult:
    """
    Validate and lightly execute a generated tool module.

    This is not a full OS container. It combines:
      1) Static AST deny-list (OS/process/network APIs)
      2) A subprocess with a stripped environment
      3) Import-time smoke_test() / register() checks

    Install is refused when safety.sandbox is false (enforced by callers).
    """
    root = harness_root()
    try:
        source = module_path.read_text(encoding="utf-8")
    except OSError as exc:
        return SandboxResult(ok=False, stdout="", stderr=f"could not read module: {exc}")

    static_issues = analyze_tool_source(source)
    if static_issues:
        detail = "; ".join(static_issues)
        return SandboxResult(
            ok=False,
            stdout="",
            stderr=f"sandbox static analysis rejected module: {detail}",
        )

    code = """
import importlib.util
import pathlib
import sys

module_path = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("candidate_tool", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load module spec")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if hasattr(module, "smoke_test"):
    module.smoke_test()
if not hasattr(module, "register"):
    raise RuntimeError("tool module must define register(registry)")
print("sandbox smoke test passed")
"""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code, str(module_path)],
            cwd=str(root),
            env=_restricted_env(root),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(ok=False, stdout="", stderr="sandbox smoke test timed out")
    except OSError as exc:
        return SandboxResult(ok=False, stdout="", stderr=f"sandbox failed to start: {exc}")

    return SandboxResult(
        ok=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
    )
