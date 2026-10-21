# CrackStack Disk Footprint

This document explains what takes space under the CrackStack root, what is safe
to delete when reclaiming disk, and what must be kept for a working portable
install.

Paths are relative to the harness root (the folder that contains `run.ps1`,
`config.toml`, and `harness/`).

## Must keep (runtime)

| Path | Why |
|------|-----|
| `harness/` | Application source (CLI, GUI, tools, agent loop). |
| `config.toml` | Model path, context, GPU layers, safety flags. |
| `run.ps1`, `run.bat`, `run.sh` | Launchers that set `CRACKSTACK_ROOT` / `PYTHONPATH`. |
| `pyproject.toml` | Package metadata and pytest config. |
| `scripts/` | Entry points, GPU wheel installers, launcher sources. |
| `runtime/python/` | Bundled portable Python per platform (Windows/macOS/Linux). Without this, only host-Python dev mode works. |
| `runtime/site-packages/` (if populated) | Optional extra packages layered on the runtime. |
| `models/` | Local GGUF (or other) model weights. The agent cannot run without at least one model. |
| `workspace/` | Default tool sandbox / project files the agent edits. |
| `plugins/` | Including `plugins/generated_tools/` if you use self-mod tools. |
| `releases/` | Signed portable binaries and release zips for distribution and offline use. |

Optional but useful to keep:

| Path | Why |
|------|-----|
| `docs/` | Release notes, checksums, signing material, this guide. |
| `README.md` | User-facing setup and GPU/context docs. |
| `tests/` | Regression suite (`python -m pytest tests` or smoke runner). |
| `state/conversations/` | Session transcripts (not required to start the app). |
| `logs/` | Audit / tool call logs (not required to start the app). |

## Safe to delete (rebuildable or disposable)

| Path | Notes |
|------|-------|
| `**/__pycache__/` | Bytecode caches. Recreated on import. |
| `**/*.pyc` | Same as above. |
| `generated/pyinstaller-build*/` | PyInstaller work dirs from packaging builds. |
| `generated/pyinstaller-spec*/` | Generated `.spec` files from packaging. |
| `generated/wheel-probe/` | Temporary wheel probe artifacts. |
| `generated/` (other tool outputs) | Archives/executables created by packaging tools. Safe if you do not need those outputs. |
| `logs/*.log` | Operational logs only. |
| `state/conversations/*.jsonl` | Old chat transcripts. Delete if you do not need history. |
| `runtime/downloads/` | Cached installer tarballs (e.g. CPython). Safe if the matching `runtime/python/` tree is already installed. |
| `runtime/wheels/` | Cached wheels used during GPU/runtime setup. Safe after install if packages already live under `runtime/python/...`. |
| `.pytest_cache/`, `.mypy_cache/`, etc. | Local tool caches if present. |

**Do not delete** `runtime/python/<platform>/` thinking it is a “build artifact” —
that tree *is* the portable interpreter and installed packages (including
`llama-cpp-python`, PySide6, etc.).

## Size expectations (order of magnitude)

| Component | Typical size |
|-----------|----------------|
| Source (`harness/`, `scripts/`, `tests/`, docs) | Tens of MB |
| Bundled Python + site packages | Several GB (especially with CUDA/Vulkan llama builds and PySide6) |
| One 14B Q4 GGUF model | ~8–9 GB |
| PyInstaller `generated/` build trees | Hundreds of MB to multi-GB if left around |
| Release zips under `releases/` | Hundreds of MB each |

Exact sizes vary by platform and which optional stacks you installed.

## Suggested cleanup commands

From the harness root (PowerShell):

```powershell
# Bytecode caches
Get-ChildItem -Recurse -Directory -Filter __pycache__ |
  Remove-Item -Recurse -Force

# PyInstaller / packaging build trees (keeps finished releases/)
if (Test-Path generated) {
  Get-ChildItem generated -Directory |
    Where-Object { $_.Name -like 'pyinstaller-*' -or $_.Name -eq 'wheel-probe' } |
    Remove-Item -Recurse -Force
}
```

After cleanup, confirm the app still starts:

```powershell
.\run.ps1 doctor
```

## What not to touch outside this tree

Sibling folders such as other projects on the same drive are unrelated. Only
paths under this CrackStack root are described here.
