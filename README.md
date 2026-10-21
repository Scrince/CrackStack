# CrackStack Codex

CrackStack Codex is a portable, local-first coding agent designed to run from
its own folder on an external drive. The desktop app presents a Codex-style task
workspace while routing all model calls to local backends such as GGUF models
through `llama-cpp-python`.

## Quick Start

Place `.gguf` models under `models/`, then run one of the root launchers:

```powershell
.\run.ps1 chat
```

Open the PySide6 desktop GUI:

```powershell
.\run.ps1 gui
```

or double-click:

```text
releases\windows\crackstack-harness-gui.exe
```

or:

```cmd
run.bat chat
```

On macOS/Linux:

```sh
./run.sh chat
```

The Windows launcher uses the bundled Python under
`runtime/python/windows-x64/`. That runtime includes the GGUF backend dependency
(`llama-cpp-python`), the HuggingFace backend stack, PySide6, and PyInstaller.
If the bundled runtime is missing, launchers fall back to host Python with a
clear warning for development only.

## Config

The default config path is `config.toml` at the harness root. All paths are
relative to the harness root:

```toml
[model]
backend = "gguf"
path = ""
context_size = 4096
gpu_layers = 0
temperature = 0.7
max_tokens = 512

[workspace]
root = "workspace"

[safety]
self_modify = false
sandbox = true
allow_outside_workspace = false
dry_run = false
max_file_bytes = 1000000
max_search_matches = 200
```

`max_file_bytes` limits tool reads and patch inputs for text files.
`max_search_matches` limits regex search output so large workspaces do not
overwhelm the prompt.

### GPU / context presets

Suggested starting points (adjust after `.\run.ps1 doctor` and a short chat).
VRAM notes assume a ~14B Q4 GGUF; smaller models leave more room for context.

| Preset | `context_size` | `gpu_layers` | `max_tokens` | Notes |
|--------|----------------|--------------|--------------|-------|
| CPU-only | 4096 | 0 | 384–512 | Slowest; safest default without a GPU wheel. |
| 8–12 GB VRAM | 6656 | 16–24 | 512 | Matches the Vulkan/CUDA installer default (`gpu_layers = 24`). Lower layers if load fails. |
| 16+ GB VRAM | 8192–16384 | 24 or `-1` | 512–1024 | `-1` tries full offload. Raise context only if RAM/VRAM allows. |
| Long context | 16384–32768 | as above | 512–1024 | Needs more system RAM for KV cache; use GUI context presets or `context_size`. |

`max_tokens` caps **completion** length per generation step (not the full
window). For multi-step tool use, 512 is a good default; 384 is fine on tight
VRAM; 1024 helps long patches when the context window can hold them.

The desktop GUI **Settings** panel (context preset/slider, GPU layers, max
tokens, temperature, dry-run, self-modify) writes the same keys back to
`config.toml` when you click **Save & reload model**. Disk layout and what you
can delete are covered in [`docs/DISK_FOOTPRINT.md`](docs/DISK_FOOTPRINT.md).

## GPU Acceleration

The portable Windows runtime can be converted from the CPU-only
`llama-cpp-python` wheel to a GPU-enabled wheel. The Vulkan wheel is the most
portable Windows GPU path and works on NVIDIA GPUs without installing the CUDA
toolkit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-llama-vulkan.ps1
```

CUDA wheels can be installed when a compatible prebuilt wheel exists for the
bundled Python version:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-llama-cuda.ps1
```

The scripts install the official GPU wheel into the bundled Python runtime,
verify that `llama.cpp` reports GPU offload support, and set `gpu_layers = 24`
in `config.toml`. Use a lower value if the model fails to load because of VRAM
pressure, or `-1` to try full offload on GPUs with enough VRAM. Run diagnostics
afterward:

```powershell
.\run.ps1 doctor
```

## Desktop App

The PySide6 desktop app provides a Codex-like local task interface: a left rail
for model selection, recent tasks, local run settings, and diagnostics; a main
task transcript; and a composer for asking the local coding model to inspect
files, edit the workspace, run tools, create archives, or explain changes.

Drag and drop files onto the composer or transcript (or use **Attach**) to
include them as context on the next send. Text files are inlined into the
prompt; binary files are attached by path only. Use the context preset or
**Context tokens** control to raise the model window (for example 8K/16K/32K),
then **Save & Reload Model** so the local GGUF backend reloads with the new
`n_ctx`. Larger context needs more RAM/VRAM.

Saving generation settings updates `config.toml` and reloads the live model so
the next prompt uses the new values.

Use `harness models` to list discovered GGUF files.

If exactly one `.gguf` file exists under `models/`, the harness can use it even
when `model.path` is empty. If multiple models are present, set `model.path` to
one of the relative paths shown by `harness models`.

Show the current config:

```powershell
.\run.ps1 config show
```

Select a discovered model by number or relative model path:

```powershell
.\run.ps1 models
.\run.ps1 config model 1
```

Run diagnostics after moving the drive to a new machine:

```powershell
.\run.ps1 doctor
```

The doctor command reports the detected platform, active Python, bundled Python
location, model discovery, optional backend dependencies, PyInstaller, and
writable state directories.

On the prepared Windows runtime, `doctor` should report bundled Python,
`llama-cpp-python`, `transformers`, and PyInstaller as `ok`. Before you add a
model, the only expected missing checks are model-related.

## Tool Calling

Phase 2 adds a prompt-based tool protocol for local models. The system prompt
injects JSON tool specs. To call a tool, the model should respond with only:

```json
{"tool": "read_file", "arguments": {"path": "notes.txt"}}
```

The agent executes the call, appends a tool observation to the conversation, and
continues until the model returns normal final text.

Backends can also opt into native tool calling by setting
`supports_native_tools = true` and implementing `generate_with_tools(...)`.
Backends that do not opt in use the prompt-based protocol above.

The conversation loop includes a lightweight context manager that preserves the
system prompt and most recent messages, dropping older turns when the configured
context window is approached.

Filesystem tools are scoped to `workspace/` by default. They reject absolute
paths and `../` escapes unless both the config and the tool call explicitly set
outside-workspace access. Write, delete, rename, create, and patch actions are
logged to `logs/audit.log`. Text reads and regex searches are bounded by the
configured safety limits.

## Self-Modification

Phase 3 adds a guarded self-modification tool:

```json
{"tool": "install_tool_module", "arguments": {"module_name": "my_tool", "source": "..."}}
```

Self-modification is disabled by default. Enable it explicitly:

```toml
[safety]
self_modify = true
sandbox = true
```

Generated tools are written under `plugins/generated_tools/`, smoke-tested in a
subprocess, then registered into the live tool registry. A generated module must
define `register(registry)`. If it defines `smoke_test()`, that function is run
before the tool is accepted.

Each self-edit snapshots the harness with git before and after the change. To
roll back recent self-modification commits:

```powershell
.\run.ps1 rollback 1
```

## Packaging

Phase 4 adds two packaging tools:

```json
{"tool": "zip_paths", "arguments": {"paths": ["app", "README.txt"], "output_path": "bundle.zip"}}
```

`zip_paths` reads files and directories from `workspace/` and writes archives
under `generated/`.

```json
{"tool": "build_executable", "arguments": {"script_path": "app.py", "output_dir": "executables"}}
```

`build_executable` invokes PyInstaller from the active portable runtime. If
PyInstaller is not vendored or installed in that runtime, the tool returns a
clear error. Outputs are written under `generated/`.

## Dry Run

Use `--dry-run` before or after `chat`/`run` to preview write-capable tool
actions:

```powershell
.\run.ps1 --dry-run run "zip the app folder"
.\run.ps1 run --dry-run "edit workspace notes without writing"
```

In the desktop GUI, enable **Dry run (no writes)** under Settings and click
**Save & reload model** so the choice is written to `config.toml` as
`safety.dry_run = true` (and reloaded for the next conversation).

In dry-run mode, filesystem writes, deletes, renames, patch edits, archive
creation, executable builds, and self-modification installs report planned
changes without applying them.

## Sessions And Logs

Every `chat` or `run` invocation writes a JSONL transcript under
`state/conversations/`. Tool call events are also appended to
`logs/tool_calls.log`.

List saved sessions:

```powershell
.\run.ps1 sessions list
```

Show a transcript:

```powershell
.\run.ps1 sessions show <session-id>
```

## Inspecting Tools

List the live tool registry:

```powershell
.\run.ps1 tools list
```

Print machine-readable JSON specs:

```powershell
.\run.ps1 tools specs
```

Print the exact tool prompt block injected into conversations:

```powershell
.\run.ps1 tools prompt
```

## Release Verification

Release-prep artifacts follow the same layout style as YellowSphere:

- `docs/SHA256SUMS` contains SHA-256 hashes for release artifacts and release
  metadata.
- `docs/SHA256SUMS.asc` is a detached ASCII-armored PGP signature for the hash
  manifest.
- Detached `*.asc` signatures live next to signed release artifacts.
- `docs/CrackStack_Release_Signing_2026_pubkey.asc` contains the public PGP
  release-signing key.
- `docs/CrackStack_Local_Code_Signing_2026.cer` contains the local
  self-signed code-signing certificate used for the Windows executable.

Release signing key:

```text
CrackStack Release Signing (2026) <release@crackstack.local>
Fingerprint: FB1B 27B8 8818 C13A DFF5 0BAE 7D20 C384 A0A9 0F16
```

Verify the signed checksum manifest:

```powershell
gpg --import docs\CrackStack_Release_Signing_2026_pubkey.asc
gpg --verify docs\SHA256SUMS.asc docs\SHA256SUMS
```

Verify the Windows executable:

```powershell
gpg --verify releases\windows\crackstack-harness.exe.asc releases\windows\crackstack-harness.exe
gpg --verify releases\windows\crackstack-harness-gui.exe.asc releases\windows\crackstack-harness-gui.exe
Get-AuthenticodeSignature releases\windows\crackstack-harness.exe
```

The Authenticode certificate is local/self-signed, so Windows will report an
untrusted root unless you explicitly trust `docs/CrackStack_Local_Code_Signing_2026.cer`.
Use the PGP signature and SHA-256 manifest as the portable verification path.

## Windows installer

See [Windows installer and signature verification](docs/WINDOWS_INSTALLER.md) for the download path and verification steps.
