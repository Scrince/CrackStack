# Security Policy

CrackStack is a local coding agent with file-system tools, persistent local
transcripts, optional generated Python tools, and a build tool that invokes
PyInstaller. It is designed for a single trusted operating-system user. It is
not a multi-user service, an execution sandbox, or a security boundary between
the model and the host account.

## Supported versions

Security fixes are developed against the current `main` branch and the latest
published release. Older releases may not receive fixes. When reporting a
problem, include the version or commit, operating system, Python/runtime
version, backend, and relevant configuration values.

## Reporting a vulnerability

Please do not publish exploit details, proof-of-concept code, secrets, or
private user data in a public issue or pull request.

1. If GitHub private vulnerability reporting is enabled for this repository,
   submit a report through
   [Report a vulnerability](https://github.com/Scrince/CrackStack/security/advisories/new).
2. If that private channel is unavailable, do not post the technical details
   publicly. Open a minimal issue asking the maintainer for a private reporting
   channel; omit payloads, affected user data, and exploitation steps until a
   private channel is established.

Include the affected version or commit, platform, configuration, attacker
preconditions, impact, a concise reproduction, and any relevant sanitized logs.
Do not attach real credentials, private keys, proprietary source, or unredacted
conversation transcripts. If a report depends on a model, plugin, or release
artifact, include its source and cryptographic hash where possible.

The repository does not currently publish a response-time commitment or bug
bounty. The maintainer should acknowledge a report, validate impact, coordinate
a fix and disclosure with the reporter, and publish a security note with the
fix. Please allow reasonable time for remediation before public disclosure.

## User security guidance

- Keep `safety.self_modify = false` unless you intentionally trust generated
  Python code. When enabled, generated modules execute in the harness process
  with the current user's operating-system permissions. The AST checks and
  subprocess smoke test are screening steps, not containment.
- Keep `safety.allow_outside_workspace = false`. An individual file-system
  operation must also request `outside_workspace = true` before a relative path
  can escape the configured workspace. Do not treat this as a prompt-injection
  defense: the model can request tools without a per-operation confirmation.
- Use `safety.dry_run = true` while reviewing planned writes, deletes, patches,
  archives, and builds. Dry-run is a preview setting, not an authorization
  mechanism or a general execution sandbox.
- Treat models, plugins, workspace files, and attachments as untrusted input.
  Prompt injection can cause the model to misuse available tools. Review
  changes and generated artifacts before using them.
- Protect the harness directory with normal operating-system account and disk
  controls. Conversation JSONL files and tool logs are plaintext and can
  contain prompts, attached text, tool arguments, file contents, paths, and
  tool results. Do not place the state or logs directory in a shared or
  world-readable location.
- Treat `build_executable` as code execution. It invokes PyInstaller against a
  Python script from the workspace and runs with the harness user's privileges.
- Verify downloaded release checksums and detached signatures using the
  verification procedure and public key in `docs/BuildReproducibility.txt`.
  Obtain the signing-key fingerprint through a trusted channel independent of
  the artifact being checked.
- Back up important workspace data. Tool history covers generated-tool files;
  it is not a general-purpose backup of the workspace or harness.

## Security scope

Reports about unauthorized file access or modification, code execution,
credential or transcript exposure, unsafe generated-tool execution, path
boundary failures, release integrity, or denial of service in supported code
paths are in scope. Purely local attacks that require the reporter to already
control the same operating-system account should state that prerequisite; the
application does not claim to isolate mutually untrusted users sharing one
account.

The detailed trust boundaries, controls, assumptions, and known limitations are
documented in [THREAT_MODEL.md](THREAT_MODEL.md). That document describes the
current implementation and is not a guarantee that every deployment or
third-party dependency has been audited.
