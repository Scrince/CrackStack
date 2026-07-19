from __future__ import annotations

from harness.tools.plugin_loader import load_generated_tools
from harness.tools.registry import ToolRegistry


def test_load_generated_tools_continues_after_broken_module(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("def register(registry):\n    raise RuntimeError('boom')\n", encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text(
        "\n".join(
            [
                "def register(registry):",
                "    registry.register(",
                "        'ok_tool',",
                "        'A working generated tool.',",
                "        {'type': 'object', 'properties': {}},",
                "        lambda: 'ok',",
                "    )",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = ToolRegistry()

    loaded = load_generated_tools(tmp_path, registry)

    assert loaded == ["good.py"]
    assert registry.run("ok_tool", {}).content == "ok"
