from __future__ import annotations

from dataclasses import dataclass
import subprocess
from pathlib import Path

from harness.paths import harness_root


@dataclass(frozen=True)
class GitSnapshot:
    committed: bool
    revision: str | None
    message: str


class SelfModificationHistory:
    def __init__(self, root: Path | None = None):
        self.root = (root or harness_root()).resolve()
        self.history_root = (self.root / "plugins" / "generated_tools").resolve()

    def _git(
        self,
        *args: str,
        check: bool = True,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.history_root,
            text=True,
            capture_output=True,
            check=check,
        )

    def ensure_repo(self) -> None:
        self.history_root.mkdir(parents=True, exist_ok=True)
        if not (self.history_root / ".git").exists():
            self._git("init", str(self.history_root), cwd=self.root)
        self._git("config", "user.name", "CrackStack Codex")
        self._git("config", "user.email", "crackstack@local.invalid")

    def snapshot(self, message: str) -> GitSnapshot:
        self.ensure_repo()
        self._git("add", "-A")
        status = self._git("status", "--porcelain").stdout.strip()
        if not status:
            rev = self.current_revision()
            return GitSnapshot(committed=False, revision=rev, message="no changes")
        self._git("commit", "-m", message)
        return GitSnapshot(committed=True, revision=self.current_revision(), message=message)

    def current_revision(self) -> str | None:
        result = self._git("rev-parse", "--verify", "HEAD", check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def rollback(self, steps: int) -> str:
        if steps < 1:
            raise ValueError("rollback steps must be >= 1")
        self.ensure_repo()
        if self.current_revision() is None:
            raise RuntimeError("no git snapshots exist yet")
        self._git("reset", "--hard", f"HEAD~{steps}")
        rev = self.current_revision()
        return rev or "no revision"
