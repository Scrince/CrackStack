from __future__ import annotations

import zipfile

from harness.config import HarnessConfig, ModelConfig, SafetyConfig, WorkspaceConfig
from harness.paths import generated_dir
from harness.tools.filesystem import FilesystemTools
from harness.tools.packaging import PackagingTools


def make_config(dry_run: bool = False) -> HarnessConfig:
    return HarnessConfig(
        model=ModelConfig(),
        workspace=WorkspaceConfig(root="workspace"),
        safety=SafetyConfig(dry_run=dry_run),
    )


def test_zip_paths_creates_archive_from_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    fs = FilesystemTools(make_config())
    fs.write_file("app/main.py", "print('hello')\n")
    fs.write_file("README.txt", "notes\n")

    result = PackagingTools(make_config()).zip_paths(["app", "README.txt"], "bundle.zip")

    assert result == "created bundle.zip"
    archive_path = generated_dir() / "bundle.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == ["README.txt", "app/main.py"]


def test_packaging_dry_run_does_not_create_zip(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    fs = FilesystemTools(make_config())
    fs.write_file("file.txt", "content\n")

    result = PackagingTools(make_config(dry_run=True)).zip_paths(["file.txt"], "dry.zip")

    assert result == "dry-run: would create dry.zip from file.txt"
    assert not (generated_dir() / "dry.zip").exists()


def test_build_executable_dry_run_reports_pyinstaller_command(monkeypatch, tmp_path):
    monkeypatch.setenv("CRACKSTACK_ROOT", str(tmp_path))
    fs = FilesystemTools(make_config())
    fs.write_file("script.py", "print('hi')\n")

    result = PackagingTools(make_config(dry_run=True)).build_executable("script.py")

    assert result.startswith("dry-run: would run ")
    assert "PyInstaller" in result
    assert "script.py" in result
