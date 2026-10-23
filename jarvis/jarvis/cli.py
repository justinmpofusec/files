"""Command line interface: `jarvis` (interactive) or `jarvis -c "open spotify"` (one shot)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from jarvis.assistant import build_jarvis
from jarvis.config import CONFIRM_MODES, Config
from jarvis.context import Context
from jarvis.llm import GeminiLLM, LLMError

BANNER = "Jarvis ready. Type a request, /tools, /reset, or /quit."


def console_confirm(name: str, args: dict[str, Any]) -> bool:
    print(f"\n  Jarvis wants to run {name}:", file=sys.stderr)
    for key, value in args.items():
        shown = value if isinstance(value, str) else json.dumps(value)
        print(f"    {key}: {shown}", file=sys.stderr)
    try:
        return input("  Allow? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="jarvis", description="Gemini-powered assistant that acts on your computer.")
    p.add_argument("-c", "--command", help="Run one request and exit.")
    p.add_argument("--dry-run", action="store_true", help="Simulate actions instead of performing them.")
    p.add_argument("--confirm", choices=CONFIRM_MODES, help="When to ask before acting (default: sensitive).")
    p.add_argument("--model", help="Gemini model id (default from JARVIS_MODEL).")
    p.add_argument("--env-file", default=".env", help="Path to a .env file with GEMINI_API_KEY etc.")
    p.add_argument("-q", "--quiet", action="store_true", help="Don't print tool activity.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, llm=None) -> int:
    args = parse_args(argv)
    config = Config.from_env(args.env_file)
    if args.dry_run:
        config.dry_run = True
    if args.confirm:
        config.confirm = args.confirm
    if args.model:
        config.model = config.vision_model = args.model

    try:
        llm = llm or GeminiLLM(config.api_key, config.model, config.vision_model)
    except LLMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    log = (lambda msg: None) if args.quiet else (lambda msg: print(f"  -> {msg}", file=sys.stderr))
    ctx = Context.create(config, llm, confirm=console_confirm, log=log)
    jarvis = build_jarvis(ctx)

    def handle(request: str) -> int:
        try:
            print(jarvis.run(request))
            return 0
        except LLMError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command:
        return handle(args.command)

    print(BANNER + (" (DRY RUN)" if config.dry_run else ""))
    while True:
        try:
            request = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not request:
            continue
        if request in ("/quit", "/exit"):
            return 0
        if request == "/reset":
            jarvis.reset()
            print("Conversation cleared.")
            continue
        if request == "/tools":
            for t in jarvis.tools:
                print(f"  {t.name}{' (asks first)' if t.sensitive else ''}: {t.description}")
            continue
        try:
            handle(request)
        except KeyboardInterrupt:
            print("\n(interrupted)")


if __name__ == "__main__":
    raise SystemExit(main())
