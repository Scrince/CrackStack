# CrackStack Threat Model

## 1. Purpose and assessment boundary

This document models the security-relevant behavior of the CrackStack local
coding-agent application: its Python CLI and GUI, model backends, tool loop,
workspace tools, generated-tool mechanism, local state, and packaging path. It
describes the source implementation, not a claim of formal verification,
penetration testing, operating-system isolation, or certification. Revalidate
it when these components or their dependencies change.

The application is intended to run as one user's local process. The operating
system account, filesystem permissions, and machine security configuration are
the primary isolation boundary. CrackStack does not provide per-user
authentication, tenant separation, a remote server API, or a policy engine
that asks a person to approve each model-requested tool call.

### In scope

- CLI and PySide6 GUI entry points.
- GGUF and Transformers model-loading/generation paths.
- Prompt construction, model output parsing, and tool dispatch.
- Workspace file reads, writes, edits, deletes, renames, searches, attachments,
  and archive creation.
- Generated Python modules and the `safety.self_modify` / `safety.sandbox`
  controls.
- PyInstaller executable builds launched by the packaging tool.
- Conversation transcripts, tool-call logs, audit logs, and generated-tool Git
  history.
- Configuration, model/runtime files, release artifacts, and their integrity.

### Out of scope

- The security of the host operating system, account, hardware, or local
  administrator privileges.
- The correctness of third-party Python packages, native extensions, GPU
  drivers, model weights, or user-installed plugins.
- Protection against a person who already controls the same OS account or can
  modify the harness installation, environment variables, model files, or
  configuration before launch.
- Confidentiality after a user copies, archives, exports, or shares data using
  mechanisms outside the application.

## 2. System model

```text
User / local files / downloaded model
                 |
                 v
       CLI or PySide6 GUI process
          |              |
          |              +--> state/conversations/*.jsonl
          |              +--> logs/tool_calls.log and logs/audit.log
          |
          +--> local model backend (GGUF or Transformers)
          |             No application account or cloud inference service
          |
          +--> model output --> parser --> ToolRegistry --> local tools
                                             |             |
                                             |             +--> workspace /
                                             |             +--> generated /
                                             |             +--> plugins/generated_tools/
                                             |             +--> PyInstaller subprocess
                                             |
                                             +--> generated Python module import
                                                  when explicitly trusted
```

The model is not a security principal. It is an untrusted decision-making
component whose text can cause tool execution. The tool registry validates
argument shape and types, but it does not infer user intent or require a human
approval step. Model output, attached files, repository content, and generated
tool source must be treated as adversarial data.

### Implementation map

| Concern | Primary implementation |
|---|---|
| Conversation loop and automatic tool dispatch | `harness/core/agent.py` (`Conversation.ask`) |
| Text tool-call parsing and repair | `harness/core/tool_calls.py` |
| Tool schema/type checks | `harness/tools/registry.py` (`coerce_tool_arguments`, `Tool.run`) |
| Workspace resolution and file operations | `harness/tools/filesystem.py` |
| Archive and executable creation | `harness/tools/packaging.py` |
| Generated-code analysis and smoke test | `harness/sandbox/runner.py` |
| Generated-module execution and registration | `harness/tools/plugin_loader.py`, `harness/tools/self_modify.py` |
| Configuration and root selection | `harness/config.py`, `harness/paths.py` |
| Conversation persistence | `harness/storage/sessions.py` |
| Tool-call and mutation logs | `harness/storage/tool_log.py`, `harness/storage/audit.py` |
| GUI attachment reading and prompt composition | `harness/gui.py` (`read_attachment_excerpt`, `build_prompt_with_attachments`) |

## 3. Assets and security objectives

| Asset | Security objective | Relevant failure |
|---|---|---|
| Workspace source and data | Prevent unintended read, overwrite, deletion, or disclosure | Prompt-driven misuse, path escape, symlink traversal, destructive tool call |
| Files outside the workspace | Keep inaccessible unless explicitly allowed | Misconfigured outside-workspace access or recursive symlink handling |
| Conversation transcripts and logs | Preserve confidentiality and integrity | Plaintext disclosure, accidental inclusion of secrets, local tampering |
| Model and generated Python | Preserve provenance and prevent untrusted code execution | Malicious/modified model, unsafe plugin, compromised dependency |
| Harness configuration and runtime | Prevent privilege or trust-boundary changes | Local tampering, wrong root/environment, unsafe runtime package |
| Generated archives and executables | Prevent unexpected content or executable behavior | Symlink inclusion, hostile input, PyInstaller hook/import execution |
| Audit and self-modification history | Support investigation and recovery | Incomplete coverage, local alteration, false assumption of backup |

Primary objectives are: constrain filesystem operations to the configured
workspace by default; require explicit opt-in for generated Python execution;
validate tool arguments deterministically; preserve local data confidentiality
under ordinary single-user file permissions; and make release provenance
checkable. These objectives are partial controls, not guarantees against
malicious code already executing as the user.

## 4. Trust boundaries

### B1 — Model output to tool dispatcher

The model returns plain text or, for a backend that supports them, native tool
calls. Current shipped GGUF and Transformers backends set
`supports_native_tools = False`; they use the JSON-like text protocol. The
conversation loop can execute a parsed tool call immediately. The loop limits
tool iterations, but there is no per-call user confirmation. JSON parsing and
schema validation mitigate malformed arguments; they do not mitigate
prompt-injection intent.

### B2 — Workspace boundary

Filesystem paths are resolved under the configured workspace. Absolute paths
are rejected. A relative path that escapes with `..` is rejected unless both
`safety.allow_outside_workspace = true` and the individual operation supplies
`outside_workspace = true`. The flag is type-checked as a Boolean. Mutations
also inspect existing path components for symlinks.

This is defense in depth, not a race-free capability boundary. Recursive
operations do not consistently reject nested symlink targets before opening
them: `search_files` can read a symlinked file encountered during traversal,
and `zip_paths` can archive a linked file's target. An attacker able to place a
symlink inside a searched or archived directory may therefore expose data
outside that directory even when direct path resolution would reject an
outside target. Filesystem changes between validation and use are also a
time-of-check/time-of-use risk. Do not treat workspace scoping as protection
against a hostile local process that can mutate the tree concurrently.

### B3 — Generated code to host process

Generated tools are skipped unless `safety.self_modify = true` and
`safety.sandbox = true`. The GUI labels the former as an explicit trust choice.
Installation performs static AST checks and a subprocess smoke test, then
imports the module in the main process. The checks are not an OS sandbox: the
AST denylist is bypassable, the smoke-test subprocess has no OS-enforced
filesystem/network/process isolation, and accepted code runs with the host
user's privileges. With `self_modify` enabled, treat generated modules as
arbitrary trusted Python code. Leave it disabled for untrusted model output.

### B4 — Application data to local storage

ConversationStore writes JSONL transcripts under `state/conversations/`.
Tool events are written to `logs/tool_calls.log`; file mutation and packaging
events are written to `logs/audit.log`. The logs are not encrypted, access
controlled beyond OS permissions, tamper-evident, or comprehensive security
audit records. Tool-call messages may include full arguments and results;
transcripts may include prompts, attachment contents, source code, and secrets.
The GUI inlines recognized text attachments into the prompt (200,000 bytes by
default, bounded by a positive `max_file_bytes` value); binary attachments are
represented by path and size. Configuration values are not range-validated:
nonpositive `max_file_bytes` values disable filesystem read limits, while a
negative value can also bypass attachment truncation. These limits are
operational safeguards for ordinary settings, not adversarial quotas.

### B5 — Build input to PyInstaller process

`build_executable` invokes the current Python interpreter and PyInstaller on a
workspace script. It uses an argument vector rather than a shell command, which
reduces shell-injection risk, but the build is not sandboxed. Python imports,
PyInstaller hooks, and build-time code can execute with the harness user's
permissions. The output directory is constrained under `generated/`; the
process itself is not confined to that directory.

### B6 — Release and dependency provenance

The project publishes checksums and detached signatures for release artifacts
and documents a signing-key fingerprint. This allows verification only when
the verifier obtains the expected fingerprint through an independent trusted
channel. The application does not continuously attest its runtime, model
weights, Python packages, or local files after installation. Optional
dependency installation scripts use package indexes and network access.

## 5. Adversaries and capabilities

1. **Prompt-injection author:** controls a workspace file, attached document,
   issue, source comment, or other text the model is asked to inspect. They can
   attempt to induce reads, writes, archive creation, or other tool calls.
2. **Malicious or compromised model source:** supplies weights that emit
   adversarial instructions or exploit backend/runtime vulnerabilities.
3. **Untrusted generated-tool author:** supplies Python code directly or
   induces a model to propose code. If the user explicitly enables
   `self_modify`, that code can execute in-process.
4. **Local concurrent process:** can modify workspace paths while the harness
   runs, race path validation, replace files, or read user-accessible logs.
5. **Supply-chain attacker:** compromises a dependency, model download,
   release artifact, signing key, build host, or package index.
6. **Resource-exhaustion source:** supplies pathological regexes, very large
   directory trees, huge models, or expensive build inputs.

The model itself is not assumed to honor the system prompt. The workspace is
not assumed to contain only benign content. The OS user is assumed to protect
the harness root and configuration from other principals.

## 6. Implemented controls

### Tool dispatch and parameters

- Tool names are resolved through a fixed registry; unknown tool names return
  errors rather than invoking arbitrary functions.
- Tool arguments are checked against declared JSON-like schemas. Unknown keys,
  missing required values, and primitive type mismatches are rejected.
- The agent bounds tool-call iterations and can observe cancellation between
  generation and execution steps.
- The model protocol includes no generic shell or command-execution tool.

These controls reduce accidental and malformed operations. They do not make a
malicious model safe and do not stop it from invoking a legitimate tool with
harmful but schema-valid arguments.

### Filesystem and output paths

- Workspace paths reject absolute inputs and resolve `..` escapes by default.
- Outside-workspace access requires both a configuration opt-in and an
  operation-level Boolean.
- Mutations reject known symlink components and use atomic replacement for
  text writes and edits.
- Text reads and patch inputs are bounded by `max_file_bytes` when positive;
  search output is bounded by `max_search_matches` when positive.
- Packaging output is resolved under `generated/`; zip inputs are resolved
  under the workspace.
- `dry_run` previews supported write/delete/rename/edit/archive/build actions.

Limits are not uniform resource quotas. Recursive traversal, regex execution,
archive creation, model memory/compute use, and build subprocess resource use
are not governed by a global CPU, memory, disk, or wall-clock budget.

### Generated tools

- `safety.self_modify` defaults to false; with it disabled, existing generated
  modules are not loaded and new modules cannot be installed.
- `safety.sandbox` defaults to true and is required by the installer. It gates
  an AST denylist and a subprocess smoke test; it does not create a security
  boundary.
- Failed generated-module registration restores the file and registry state.
- Generated-tool Git history is limited to `plugins/generated_tools/` and is
  not a backup of the workspace.

### Local data and release artifacts

- Conversation, tool-call, and audit records are stored locally.
- Release documentation provides detached-signature and checksum verification
  instructions.
- The core model backends use local model paths. The application layer has no
  account service or remote inference endpoint. This is not enforced network
  isolation: libraries, install scripts, plugins, PyInstaller hooks, or model
  code can have their own network behavior.

## 7. Threat analysis

| ID | Threat scenario | Existing mitigation | Residual risk / disposition |
|---|---|---|---|
| TM-01 | A document tells the model to read secrets, overwrite code, or create a malicious artifact. | Workspace root checks; typed arguments; no shell tool; default outside-workspace deny. | Tool calls run without per-call approval. Prompt injection remains in scope; review model actions and keep sensitive files outside the workspace. |
| TM-02 | A model constructs `../` or absolute paths to access another directory. | Absolute paths rejected; escape requires both global config and per-call flag. | Enabling outside-workspace access broadens the tool's authority. The model may set the per-call flag if global config allows it. |
| TM-03 | A symlink inside a recursive search/archive tree points to a secret file. | Direct resolved paths are checked; mutation paths inspect symlink components. | Recursive search and zip handling can follow nested symlink files. Known limitation; avoid untrusted symlinks in traversed trees and do not search/archive sensitive roots. |
| TM-04 | An attacker races a symlink or path replacement after validation. | Resolved paths and component checks reduce ordinary traversal. | Path checks and use are not atomic/openat-style capability operations. A concurrent local writer can race them. |
| TM-05 | Generated Python bypasses the AST denylist and executes host commands or reads arbitrary files. | `self_modify` defaults false; generated modules are skipped unless explicitly enabled; UI and docs state the trust implication. | With `self_modify=true`, code executes in-process with user privileges. The analyzer and smoke test are not containment. Use only for reviewed code. |
| TM-06 | A generated module partially registers tools and then fails. | Registry/file state is restored when loading or registration raises. | This is transactional failure handling, not a defense against malicious code that runs before raising. |
| TM-07 | PyInstaller executes attacker-controlled workspace code or hooks. | Output path is constrained; subprocess arguments avoid shell parsing. | Build execution is unsandboxed and runs with user privileges. Build only reviewed source and dependencies. |
| TM-08 | Prompt, attached text, tool arguments, or file contents appear in local logs. | Data remains in local application storage by default. | Logs and transcripts are plaintext and include sensitive content. Protect, back up, and remove them using OS controls. No encryption/retention policy is implemented. |
| TM-09 | A malicious model or package compromises the process. | Local paths and signed release artifacts can support provenance checks. | Model weights, Python packages, native libraries, and GPU stack are executable or parser inputs. Verify provenance; no runtime attestation is provided. |
| TM-10 | Pathological regex or recursive tree causes CPU or I/O exhaustion. | File and match limits bound some input and output sizes. | Search traversal and Python regex runtime have no timeout or global work budget. Do not run searches over hostile, huge trees with untrusted patterns. |
| TM-11 | A user trusts audit logs as a complete, tamper-proof forensic record. | Mutations and packaging actions append audit events; tool calls have a separate log. | Reads are not audited; logs can be modified by the same user, are unencrypted, and may omit lower-level side effects. They are operational traces, not a security ledger. |
| TM-12 | CLI session identifier traversal reads a different local JSONL file. | None for a caller-supplied session ID; the session list itself only enumerates conversation files. | `read_session` forms a path from the supplied session ID without strict identifier validation, so absolute or traversal IDs may resolve elsewhere. A local caller should be treated as already exercising the same account; this remains a hardening gap. |

## 8. Configuration posture

| Setting | Default | Security meaning |
|---|---:|---|
| `safety.self_modify` | `false` | When false, generated modules are skipped and installation is denied. When true, generated Python is trusted to execute in-process. |
| `safety.sandbox` | `true` | Enables static checks and subprocess smoke testing for generated modules. It is not OS isolation. Setting false also prevents generated-module loading/installation. |
| `safety.allow_outside_workspace` | `false` | Must be true, together with a per-call `outside_workspace=true`, for relative paths that resolve outside the workspace. |
| `safety.dry_run` | `false` | When true, supported mutation/build tools preview their planned operation. It does not prevent reads, model inference, or arbitrary code in trusted plugins. |
| `safety.max_file_bytes` | `1,000,000` | Bounds supported text reads and patch inputs when positive. It is not a global I/O or memory limit. |
| `safety.max_search_matches` | `200` | Bounds returned regex matches when positive; it does not bound traversal cost or regex runtime. |

Configuration is local plaintext. A malicious process with write access can
change the workspace, model path, generated-tool trust switch, and other policy
values before launch. The `CRACKSTACK_ROOT` environment variable can redirect
the harness root; the launcher environment is therefore part of the trusted
configuration boundary.

## 9. Operational assumptions and recommendations

- Run under a dedicated OS account if the workspace or plugins are
  semi-trusted. Do not run as administrator/root.
- Keep `self_modify` and `allow_outside_workspace` disabled for ordinary use.
- Treat changing `self_modify` to true as granting generated code the same
  authority as the harness process; inspect every generated module first.
- Store only the files the model needs under the workspace. Keep credentials,
  signing keys, browser profiles, SSH keys, and unrelated projects elsewhere.
- Review diffs and generated archives. Keep independent backups; the tool's
  local snapshots are not an immutable recovery point.
- Protect and periodically clear local logs if they contain sensitive data.
- Verify release artifacts against a trusted copy of the signing-key
  fingerprint. Verify package and model provenance separately.
- Use OS-level network restrictions if offline operation is a hard security
  requirement. “Local-first” does not disable networking in arbitrary Python
  dependencies or user-supplied code.

## 10. Review cadence

Update this model when tool capabilities, workspace resolution, generated-code
execution, persistence, backend loading, build behavior, release signing, or
default configuration changes. Security fixes should add regression coverage
for the violated invariant and update `SECURITY.md` if user guidance or the
reporting process changes.
