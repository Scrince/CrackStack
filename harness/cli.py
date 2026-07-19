from __future__ import annotations

import argparse
import sys

from .backends import GenerateConfig, create_backend
from .config import load_config
from .config_commands import select_model, show_config
from .core.agent import Conversation
from .core.context import ContextManager
from .doctor import format_checks, run_checks
from .models import discover_gguf_models, display_model_path
from .paths import ensure_base_dirs, harness_root, plugins_dir
from .storage.history import SelfModificationHistory
from .storage.sessions import ConversationStore, list_sessions, read_session
from .storage.tool_log import log_tool_event
from .tools import (
    ToolRegistry,
    register_filesystem_tools,
    register_packaging_tools,
    register_self_modify_tools,
)
from .tools.plugin_loader import load_generated_tools


def _tool_log(kind: str, message: str, session_id: str | None = None) -> None:
    if session_id is not None:
        log_tool_event(session_id, kind, message)
    print(f"[tool:{kind}] {message}", file=sys.stderr)


def _tool_registry(config) -> ToolRegistry:
    registry = ToolRegistry()
    register_filesystem_tools(registry, config)
    register_packaging_tools(registry, config)
    load_generated_tools(
        plugins_dir() / "generated_tools",
        registry,
        sandbox=config.safety.sandbox,
    )
    register_self_modify_tools(registry, config)
    return registry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--dry-run", action="store_true", help="Show planned writes without applying them.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="Open the CrackStack desktop GUI.")
    sub.add_parser("models", help="List discovered GGUF models under models/.")
    sub.add_parser("doctor", help="Check portable runtime, models, dependencies, and writable state.")

    tools_cmd = sub.add_parser("tools", help="Inspect registered tools.")
    tools_sub = tools_cmd.add_subparsers(dest="tools_command")
    tools_sub.add_parser("list", help="List registered tool names.")
    tools_sub.add_parser("specs", help="Print registered tool JSON specs.")
    tools_sub.add_parser("prompt", help="Print the tool prompt block injected into conversations.")

    config_cmd = sub.add_parser("config", help="Show or update harness configuration.")
    config_sub = config_cmd.add_subparsers(dest="config_command")
    config_sub.add_parser("show", help="Print config.toml.")
    model_cmd = config_sub.add_parser("model", help="Set model.path from discovered models.")
    model_cmd.add_argument("model_ref", help="Model number or relative model path from harness models.")

    chat = sub.add_parser("chat", help="Start a streaming chat session.")
    chat.add_argument("--once", help="Send one prompt and exit.")
    chat.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show planned writes without applying them.",
    )

    run = sub.add_parser("run", help="Run a single prompt and print the response.")
    run.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show planned writes without applying them.",
    )
    run.add_argument("task", nargs="+")

    rollback = sub.add_parser("rollback", help="Rollback self-modification history by N commits.")
    rollback.add_argument("steps", type=int)

    sessions = sub.add_parser("sessions", help="List or show local conversation sessions.")
    sessions_sub = sessions.add_subparsers(dest="sessions_command")
    sessions_sub.add_parser("list", help="List saved sessions.")
    show = sessions_sub.add_parser("show", help="Show a saved session transcript.")
    show.add_argument("session_id")
    return parser


def list_models() -> int:
    models = discover_gguf_models()
    if not models:
        print("No .gguf models found under models/.")
        return 0
    for model in models:
        print(display_model_path(model))
    return 0


def _conversation(dry_run: bool = False) -> Conversation:
    config = load_config(dry_run=True if dry_run else None)
    backend = create_backend(config.model)
    gen_config = GenerateConfig(
        max_tokens=config.model.max_tokens,
        temperature=config.model.temperature,
    )
    registry = _tool_registry(config)
    store = ConversationStore()
    return Conversation(
        backend=backend,
        generate_config=gen_config,
        tools=registry,
        tool_observer=lambda kind, message: _tool_log(kind, message, store.session_id),
        context_manager=ContextManager(context_window=config.model.context_size),
        store=store,
    )


def run_once(prompt: str, dry_run: bool = False) -> int:
    try:
        convo = _conversation(dry_run=dry_run)
    except Exception as exc:
        print(f"Cannot start model backend: {exc}", file=sys.stderr)
        return 1
    for chunk in convo.stream_ask(prompt):
        print(chunk, end="", flush=True)
    print()
    return 0


def chat_loop(initial_prompt: str | None = None, dry_run: bool = False) -> int:
    try:
        convo = _conversation(dry_run=dry_run)
    except Exception as exc:
        print(f"Cannot start model backend: {exc}", file=sys.stderr)
        return 1
    print(f"CrackStack harness root: {harness_root()}")
    if dry_run:
        print("Dry-run mode: write-capable tools will report planned changes only.")
    print("Type /exit to quit.")

    prompt = initial_prompt
    while True:
        if prompt is None:
            try:
                prompt = input("> ")
            except EOFError:
                print()
                return 0
        if prompt.strip() in {"/exit", "/quit"}:
            return 0
        for chunk in convo.stream_ask(prompt):
            print(chunk, end="", flush=True)
        print()
        prompt = None


def main(argv: list[str] | None = None) -> int:
    ensure_base_dirs()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "gui":
        from harness.gui import main as gui_main

        return gui_main()
    if args.command == "models":
        return list_models()
    if args.command == "doctor":
        print(format_checks(run_checks(load_config())))
        return 0
    if args.command == "config":
        if args.config_command == "model":
            try:
                print(select_model(args.model_ref))
            except Exception as exc:
                print(f"Config update failed: {exc}", file=sys.stderr)
                return 1
            return 0
        print(show_config())
        return 0
    if args.command == "tools":
        registry = _tool_registry(load_config())
        if args.tools_command == "specs":
            import json

            print(json.dumps(registry.specs(), indent=2, sort_keys=True))
            return 0
        if args.tools_command == "prompt":
            print(registry.prompt_block())
            return 0
        for spec in registry.specs():
            print(f"{spec['name']}\t{spec['description']}")
        return 0
    if args.command == "chat":
        return chat_loop(args.once, dry_run=args.dry_run)
    if args.command == "run":
        return run_once(" ".join(args.task), dry_run=args.dry_run)
    if args.command == "rollback":
        try:
            revision = SelfModificationHistory().rollback(args.steps)
        except Exception as exc:
            print(f"Rollback failed: {exc}", file=sys.stderr)
            return 1
        else:
            print(f"Rolled back to {revision}")
            return 0
    if args.command == "sessions":
        if args.sessions_command == "show":
            try:
                records = read_session(args.session_id)
            except FileNotFoundError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            for record in records:
                payload = record.get("payload", {})
                if record.get("type") == "message":
                    role = payload.get("role", "event")
                    content = payload.get("content", "")
                    print(f"{role}: {content}")
                else:
                    print(record)
            return 0
        for session in list_sessions():
            print(f"{session.session_id}\t{session.size} bytes")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
