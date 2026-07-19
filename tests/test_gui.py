from __future__ import annotations

from pathlib import Path

from harness.gui import (
    FileAttachment,
    build_prompt_with_attachments,
    is_likely_text_file,
    read_attachment_excerpt,
)


def test_gui_module_imports():
    import harness.gui as gui

    assert callable(gui.main)
    assert callable(gui.build_prompt_with_attachments)


def test_is_likely_text_file():
    assert is_likely_text_file(Path("main.py"))
    assert is_likely_text_file(Path("README.md"))
    assert is_likely_text_file(Path("Dockerfile"))
    assert not is_likely_text_file(Path("model.gguf"))
    assert not is_likely_text_file(Path("photo.png"))


def test_read_attachment_excerpt_text(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    kind, body = read_attachment_excerpt(target)
    assert kind == "text"
    assert "print('hello')" in body


def test_read_attachment_excerpt_truncates(tmp_path: Path):
    target = tmp_path / "big.txt"
    target.write_text("x" * 5000, encoding="utf-8")
    kind, body = read_attachment_excerpt(target, max_bytes=100)
    assert kind == "truncated"
    assert "truncated" in body
    assert body.startswith("x" * 100)


def test_read_attachment_excerpt_binary(tmp_path: Path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\x00\x01\x02\x03")
    kind, body = read_attachment_excerpt(target)
    assert kind == "binary"
    assert "Binary file" in body


def test_build_prompt_with_attachments(tmp_path: Path):
    a = tmp_path / "a.py"
    b = tmp_path / "notes.md"
    a.write_text("def f():\n    return 1\n", encoding="utf-8")
    b.write_text("# notes\n", encoding="utf-8")
    attachments = [
        FileAttachment(path=a, size_bytes=a.stat().st_size),
        FileAttachment(path=b, size_bytes=b.stat().st_size),
    ]
    prompt = build_prompt_with_attachments("Refactor this helper.", attachments)
    assert "Refactor this helper." in prompt
    assert "Attached files" in prompt
    assert "### File:" in prompt
    assert "def f():" in prompt
    assert "# notes" in prompt


def test_build_prompt_without_attachments_is_identity():
    assert build_prompt_with_attachments("hello", []) == "hello"
