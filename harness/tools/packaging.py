from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from harness.config import HarnessConfig
from harness.paths import generated_dir
from harness.storage.audit import log_audit
from harness.tools.filesystem import _resolve_workspace_path, _workspace
from harness.tools.registry import ToolRegistry


def _resolve_generated_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        raise ValueError("absolute output paths are not allowed")
    resolved = (generated_dir() / raw).resolve()
    base = generated_dir().resolve()
    if base != resolved and base not in resolved.parents:
        raise ValueError("output path escapes generated directory")
    return resolved


class PackagingTools:
    def __init__(self, config: HarnessConfig):
        self.config = config

    def zip_paths(self, paths: list[str], output_path: str) -> str:
        if not paths:
            raise ValueError("paths must not be empty")
        output = _resolve_generated_path(output_path)
        if output.suffix.lower() != ".zip":
            output = output.with_suffix(".zip")
        resolved_inputs = [_resolve_workspace_path(self.config, path) for path in paths]

        if self.config.safety.dry_run:
            listed = ", ".join(Path(path).as_posix() for path in paths)
            return f"dry-run: would create {output.relative_to(generated_dir()).as_posix()} from {listed}"

        output.parent.mkdir(parents=True, exist_ok=True)
        workspace = _workspace(self.config)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for input_path in resolved_inputs:
                if input_path.is_dir():
                    for file_path in sorted(item for item in input_path.rglob("*") if item.is_file()):
                        archive.write(file_path, file_path.relative_to(workspace).as_posix())
                else:
                    archive.write(input_path, input_path.relative_to(workspace).as_posix())
        log_audit("zip_paths", output, {"inputs": paths})
        return f"created {output.relative_to(generated_dir()).as_posix()}"

    def build_executable(self, script_path: str, output_dir: str = "executables") -> str:
        script = _resolve_workspace_path(self.config, script_path)
        if not script.exists():
            raise FileNotFoundError(f"script not found: {script_path}")
        if script.suffix.lower() != ".py":
            raise ValueError("script_path must point to a Python script")

        output = _resolve_generated_path(output_dir)
        build = _resolve_generated_path("pyinstaller-build")
        spec = _resolve_generated_path("pyinstaller-spec")
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--distpath",
            str(output),
            "--workpath",
            str(build),
            "--specpath",
            str(spec),
            str(script),
        ]

        if self.config.safety.dry_run:
            return "dry-run: would run " + " ".join(command)
        if shutil.which("pyinstaller") is None:
            check = subprocess.run(
                [sys.executable, "-m", "PyInstaller", "--version"],
                text=True,
                capture_output=True,
            )
            if check.returncode != 0:
                raise RuntimeError("PyInstaller is not available in this runtime")

        output.mkdir(parents=True, exist_ok=True)
        build.mkdir(parents=True, exist_ok=True)
        spec.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        log_audit("build_executable", output, {"script": script_path})
        return f"built executable in {output.relative_to(generated_dir()).as_posix()}"


def register_packaging_tools(registry: ToolRegistry, config: HarnessConfig) -> None:
    tools = PackagingTools(config)
    registry.register(
        "zip_paths",
        "Create a zip archive from workspace files or directories under generated/.",
        {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
                "output_path": {"type": "string"},
            },
            "required": ["paths", "output_path"],
        },
        tools.zip_paths,
    )
    registry.register(
        "build_executable",
        "Build a standalone executable from a workspace Python script using PyInstaller.",
        {
            "type": "object",
            "properties": {
                "script_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "executables"},
            },
            "required": ["script_path"],
        },
        tools.build_executable,
    )
