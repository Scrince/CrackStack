from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import platform
from pathlib import Path
import subprocess
import sys

from harness.config import HarnessConfig
from harness.models import discover_gguf_models, display_model_path
from harness.paths import (
    generated_dir,
    harness_root,
    logs_dir,
    models_dir,
    runtime_dir,
    state_dir,
    workspace_dir,
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    if system == "darwin" and machine == "arm64":
        return "macos-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "macos-x64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x64"
    return f"{system}-{machine}"


def _is_importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _can_write(directory: Path) -> bool:
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / ".write-check"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _llama_gpu_detail() -> tuple[bool, str]:
    try:
        from llama_cpp import llama_cpp as llama_lib
    except Exception as exc:
        return False, f"cannot inspect llama_cpp: {exc}"
    supports = getattr(llama_lib, "llama_supports_gpu_offload", None)
    if supports is None:
        return False, "llama_supports_gpu_offload unavailable"
    try:
        ok = bool(supports())
    except Exception as exc:
        return False, f"gpu support check failed: {exc}"
    return ok, "llama.cpp GPU offload enabled" if ok else "CPU-only llama.cpp build"


def _nvidia_gpu_detail() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,compute_cap,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        return False, "nvidia-smi not available"
    detail = "; ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
    return bool(detail), detail or "no NVIDIA GPU reported"


def run_checks(config: HarnessConfig) -> list[Check]:
    key = platform_key()
    root = harness_root()
    bundled_python = runtime_dir() / "python" / key
    if key == "windows-x64":
        python_exe = bundled_python / "python.exe"
    else:
        python_exe = bundled_python / "bin" / "python"

    models = discover_gguf_models()
    llama_gpu_ok, llama_gpu_detail = _llama_gpu_detail() if _is_importable("llama_cpp") else (False, "import llama_cpp")
    nvidia_ok, nvidia_detail = _nvidia_gpu_detail()
    checks = [
        Check("harness root", root.exists(), str(root)),
        Check("platform", True, key),
        Check("active python", True, sys.executable),
        Check(
            "bundled python",
            python_exe.exists(),
            str(python_exe) if python_exe.exists() else f"missing: {python_exe}",
        ),
        Check(
            "models",
            bool(models),
            ", ".join(display_model_path(model) for model in models[:5])
            if models
            else f"no .gguf files found under {models_dir()}",
        ),
        Check("configured model", config.model.resolved_path is not None, config.model.path or "not set"),
        Check("llama-cpp-python", _is_importable("llama_cpp"), "import llama_cpp"),
        Check("llama.cpp GPU offload", llama_gpu_ok, llama_gpu_detail),
        Check("NVIDIA GPU", nvidia_ok, nvidia_detail),
        Check("transformers", _is_importable("transformers"), "import transformers"),
        Check("PyInstaller", _is_importable("PyInstaller"), "python -m PyInstaller"),
    ]

    for name, directory in (
        ("workspace writable", workspace_dir()),
        ("logs writable", logs_dir()),
        ("state writable", state_dir()),
        ("generated writable", generated_dir()),
    ):
        checks.append(Check(name, _can_write(directory), str(directory)))
    return checks


def format_checks(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        status = "ok" if check.ok else "missing"
        lines.append(f"{status:7} {check.name}: {check.detail}")
    return "\n".join(lines)
