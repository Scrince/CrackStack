from __future__ import annotations

from pathlib import Path
import re
import shutil

from harness.config import HarnessConfig
from harness.storage.atomic import atomic_write_text
from harness.storage.audit import log_audit
from harness.tools.registry import ToolRegistry


def _workspace(config: HarnessConfig) -> Path:
    return config.workspace.resolved_root.resolve()


def _resolve_workspace_path(config: HarnessConfig, path: str, outside_workspace: bool = False) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        raise ValueError("absolute paths are not allowed")
    base = _workspace(config)
    resolved = (base / raw).resolve()
    if base != resolved and base not in resolved.parents:
        if not (outside_workspace and config.safety.allow_outside_workspace):
            raise ValueError("path escapes workspace root")
    return resolved


def _assert_no_symlink_components(base: Path, relative: Path) -> None:
    """Refuse mutations that walk through or target a symlink (no follow)."""
    current = base
    for part in relative.parts:
        if part in ("", "."):
            continue
        current = current / part
        try:
            if current.is_symlink():
                raise ValueError("refusing to mutate through a symlink")
        except OSError as exc:
            raise ValueError(f"could not inspect path component: {exc}") from exc
        if not current.exists():
            break


def _resolve_mutation_path(config: HarnessConfig, path: str, outside_workspace: bool = False) -> Path:
    """Resolve a workspace path for write/delete/rename, blocking symlink targets."""
    raw = Path(path)
    if raw.is_absolute():
        raise ValueError("absolute paths are not allowed")
    base = _workspace(config)
    _assert_no_symlink_components(base, raw)
    return _resolve_workspace_path(config, path, outside_workspace)


def _enforce_text_read_limit(config: HarnessConfig, target: Path) -> None:
    max_bytes = config.safety.max_file_bytes
    if max_bytes > 0 and target.exists() and target.is_file() and target.stat().st_size > max_bytes:
        raise ValueError(f"file exceeds max_file_bytes ({max_bytes})")


def _display_search_path(config: HarnessConfig, file_path: Path, outside_workspace: bool) -> str:
    workspace = _workspace(config)
    try:
        return file_path.relative_to(workspace).as_posix()
    except ValueError:
        if outside_workspace and config.safety.allow_outside_workspace:
            return file_path.resolve().as_posix()
        raise


def _apply_simple_unified_diff(original: str, patch: str) -> str:
    original_lines = original.splitlines(keepends=True)
    result: list[str] = []
    source_index = 0
    patch_lines = patch.splitlines(keepends=True)
    hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    index = 0

    while index < len(patch_lines):
        line = patch_lines[index]
        if line.startswith("--- ") or line.startswith("+++ "):
            index += 1
            continue
        match = hunk_re.match(line)
        if not match:
            raise ValueError(f"unsupported patch line: {line.rstrip()}")

        old_start_raw = int(match.group(1))
        old_start = max(old_start_raw - 1, 0)
        result.extend(original_lines[source_index:old_start])
        source_index = old_start
        index += 1

        while index < len(patch_lines) and not patch_lines[index].startswith("@@ "):
            hunk_line = patch_lines[index]
            if hunk_line.startswith("\\ No newline at end of file"):
                index += 1
                continue
            marker = hunk_line[:1]
            payload = hunk_line[1:]
            if marker == " ":
                if source_index >= len(original_lines) or original_lines[source_index] != payload:
                    raise ValueError("patch context does not match file")
                result.append(original_lines[source_index])
                source_index += 1
            elif marker == "-":
                if source_index >= len(original_lines) or original_lines[source_index] != payload:
                    raise ValueError("patch deletion does not match file")
                source_index += 1
            elif marker == "+":
                result.append(payload)
            else:
                raise ValueError(f"unsupported hunk marker: {marker}")
            index += 1

    result.extend(original_lines[source_index:])
    return "".join(result)


class FilesystemTools:
    def __init__(self, config: HarnessConfig):
        self.config = config

    def list_dir(self, path: str = ".", outside_workspace: bool = False) -> list[str]:
        target = _resolve_workspace_path(self.config, path, outside_workspace)
        if not target.exists():
            return []
        if not target.is_dir():
            raise ValueError("path is not a directory")
        return sorted(item.name + ("/" if item.is_dir() else "") for item in target.iterdir())

    def read_file(self, path: str, outside_workspace: bool = False) -> str:
        target = _resolve_workspace_path(self.config, path, outside_workspace)
        _enforce_text_read_limit(self.config, target)
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str, outside_workspace: bool = False) -> str:
        target = _resolve_mutation_path(self.config, path, outside_workspace)
        if self.config.safety.dry_run:
            return f"dry-run: would write {path} ({len(content.encode('utf-8'))} bytes)"
        atomic_write_text(target, content)
        log_audit("write_file", target, {"bytes": len(content.encode("utf-8"))})
        return f"wrote {path}"

    def create_dir(self, path: str, outside_workspace: bool = False) -> str:
        target = _resolve_mutation_path(self.config, path, outside_workspace)
        if self.config.safety.dry_run:
            return f"dry-run: would create directory {path}"
        target.mkdir(parents=True, exist_ok=True)
        log_audit("create_dir", target)
        return f"created directory {path}"

    def delete_path(self, path: str, outside_workspace: bool = False) -> str:
        target = _resolve_mutation_path(self.config, path, outside_workspace)
        if self.config.safety.dry_run:
            return f"dry-run: would delete {path}"
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        log_audit("delete_path", target)
        return f"deleted {path}"

    def rename_path(
        self,
        old_path: str,
        new_path: str,
        outside_workspace: bool = False,
    ) -> str:
        old_target = _resolve_mutation_path(self.config, old_path, outside_workspace)
        new_target = _resolve_mutation_path(self.config, new_path, outside_workspace)
        if self.config.safety.dry_run:
            return f"dry-run: would rename {old_path} to {new_path}"
        new_target.parent.mkdir(parents=True, exist_ok=True)
        old_target.replace(new_target)
        log_audit("rename_path", new_target, {"old_path": str(old_target)})
        return f"renamed {old_path} to {new_path}"

    def search_files(
        self,
        pattern: str,
        path: str = ".",
        outside_workspace: bool = False,
    ) -> list[dict[str, object]]:
        root = _resolve_workspace_path(self.config, path, outside_workspace)
        regex = re.compile(pattern)
        matches: list[dict[str, object]] = []
        files = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        for file_path in files:
            try:
                _enforce_text_read_limit(self.config, file_path)
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, ValueError):
                continue
            for line_no, line in enumerate(lines, start=1):
                if regex.search(line):
                    matches.append(
                        {
                            "path": _display_search_path(self.config, file_path, outside_workspace),
                            "line": line_no,
                            "text": line,
                        }
                    )
                    if (
                        self.config.safety.max_search_matches > 0
                        and len(matches) >= self.config.safety.max_search_matches
                    ):
                        return matches
        return matches

    def edit_file(
        self,
        path: str,
        patch: str,
        dry_run: bool = False,
        outside_workspace: bool = False,
    ) -> str:
        target = _resolve_mutation_path(self.config, path, outside_workspace)
        _enforce_text_read_limit(self.config, target)
        original = target.read_text(encoding="utf-8")
        updated = _apply_simple_unified_diff(original, patch)
        if dry_run or self.config.safety.dry_run:
            return f"dry-run: would patch {path}\n{updated}"
        atomic_write_text(target, updated)
        log_audit("edit_file", target, {"patch_bytes": len(patch.encode("utf-8"))})
        return f"patched {path}"


def register_filesystem_tools(registry: ToolRegistry, config: HarnessConfig) -> None:
    tools = FilesystemTools(config)
    registry.register(
        "list_dir",
        "List entries in a workspace directory.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": [],
        },
        tools.list_dir,
    )
    registry.register(
        "read_file",
        "Read a UTF-8 text file from the workspace.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
        tools.read_file,
    )
    registry.register(
        "write_file",
        "Write a UTF-8 text file inside the workspace using an atomic replace.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        },
        tools.write_file,
    )
    registry.register(
        "create_dir",
        "Create a directory inside the workspace.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
        tools.create_dir,
    )
    registry.register(
        "delete_path",
        "Delete a file or directory inside the workspace.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
        tools.delete_path,
    )
    registry.register(
        "rename_path",
        "Rename or move a file or directory inside the workspace.",
        {
            "type": "object",
            "properties": {
                "old_path": {"type": "string"},
                "new_path": {"type": "string"},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["old_path", "new_path"],
        },
        tools.rename_path,
    )
    registry.register(
        "search_files",
        "Search UTF-8 workspace files with a regular expression.",
        {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["pattern"],
        },
        tools.search_files,
    )
    registry.register(
        "edit_file",
        "Apply a simple unified diff patch to a workspace file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "patch": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False},
                "outside_workspace": {"type": "boolean", "default": False},
            },
            "required": ["path", "patch"],
        },
        tools.edit_file,
    )
