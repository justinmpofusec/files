"""Command line interface.

    jarvis                      type requests
    jarvis --voice              press Enter, speak; Jarvis answers out loud
    jarvis -c "open spotify"    one request and exit
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, Callable

from jarvis.assistant import build_jarvis
from jarvis.config import CONFIRM_MODES, Config
from jarvis.context import Context
from jarvis.llm import GeminiLLM, LLMError
from jarvis.voice import Listener, Speaker

BANNER = "Jarvis ready. Type a request, /tools, /log, /reset, or /quit."
VOICE_BANNER = "Voice mode: press Enter and speak (or type a request). /quit to exit."

# How each action is described when Jarvis asks for permission (also spoken in voice mode).
ACTION_PHRASES = {
    "open_app": "open {app_name}",
    "open_url": "open {url}",
    "web_search": "search the web for {query}",
    "open_path": "open {path}",
    "run_shell_command": "run the command: {command}",
    "run_applescript": "run an AppleScript",
    "send_whatsapp": "send a WhatsApp to {recipient} saying: {message}",
    "send_imessage": "send an iMessage to {recipient} saying: {message}",
    "click_on": "click {description}",
    "click_at": "click at {x}, {y}",
    "move_mouse": "move the mouse to {x}, {y}",
    "type_text": "type: {text}",
    "press_key": "press {key}",
    "hotkey": "press {keys}",
    "scroll": "scroll {amount}",
    "blender_run_script": "run a Blender script",
    "blender_render": "render {blend_file}",
    "blender_open_gui": "open Blender",
}


def describe_action(name: str, args: dict[str, Any]) -> str:
    """One-line, speakable summary of an action (full values are printed separately when long)."""
    template = ACTION_PHRASES.get(name)
    if template:
        fmt = {k: "+".join(v) if isinstance(v, list) else v for k, v in args.items()}
        try:
            text = template.format(**fmt)
            return " / ".join(line.strip() for line in text.splitlines() if line.strip())
        except (KeyError, IndexError):
            pass
    return name.replace("_", " ")


class ConsoleConfirmer:
    """Asks the user before each action. Answers: y = yes, a = yes to everything for the rest of this
    request, n/Enter = no, any other text = no, and do this instead (passed to Jarvis)."""

    def __init__(self, speaker: Speaker | None = None, read: Callable[[str], str] | None = None) -> None:
        self.speaker = speaker
        self.read = read or (lambda prompt: input(prompt))
        self.allow_all = False

    def new_request(self) -> None:
        self.allow_all = False

    def __call__(self, name: str, args: dict[str, Any]) -> bool | str:
        if self.allow_all:
            return True
        summary = describe_action(name, args)
        print(f"\n  Jarvis wants to {summary}", file=sys.stderr)
        for key, value in args.items():
            shown = value if isinstance(value, str) else json.dumps(value)
            if shown not in summary:  # anything the one-line summary doesn't already show, e.g. a script
                print(f"    {key}:\n      " + shown.replace("\n", "\n      "), file=sys.stderr)
        if self.speaker:
            self.speaker.say(f"May I {summary}?")
        try:
            answer = self.read("  Allow? [y]es / [n]o / [a]ll for this request / or type what to do instead: ").strip()
        except EOFError:
            return False
        low = answer.lower()
        if low in ("y", "yes"):
            return True
        if low in ("a", "all"):
            self.allow_all = True
            return True
        if low in ("", "n", "no"):
            return False
        return answer


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="jarvis", description="Gemini-powered assistant that acts on your computer.")
    p.add_argument("-c", "--command", help="Run one request and exit.")
    p.add_argument("--voice", action="store_true", help="Talk to Jarvis (press Enter to speak) and hear replies.")
    p.add_argument("--speak", action="store_true", help="Read replies aloud (typing still works).")
    p.add_argument("--dry-run", action="store_true", help="Simulate actions instead of performing them.")
    p.add_argument("--confirm", choices=CONFIRM_MODES,
                   help="When to ask permission: always, actions (default), sensitive, never.")
    p.add_argument("--model", help="Gemini model id (default from JARVIS_MODEL).")
    p.add_argument("--env-file", default=".env", help="Path to a .env file with GEMINI_API_KEY etc.")
    p.add_argument("-q", "--quiet", action="store_true", help="Don't print tool activity.")
    return p.parse_args(argv)


def listening_cue(os_name: str) -> None:
    print("  Listening... (stop talking to finish)", file=sys.stderr)
    if os_name == "Darwin":
        try:
            subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])
        except OSError:
            pass


def main(argv: list[str] | None = None, llm=None, listener: Listener | None = None,
         speaker: Speaker | None = None) -> int:
    args = parse_args(argv)
    config = Config.from_env(args.env_file)
    if args.dry_run:
        config.dry_run = True
    if args.confirm:
        config.confirm = args.confirm
    if args.model:
        config.model = config.vision_model = args.model
    if args.voice or args.speak:
        config.speak = True

    try:
        llm = llm or GeminiLLM(config.api_key, config.model, config.vision_model)
    except LLMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if config.speak:
        speaker = speaker or Speaker(config.os_name, config.voice, config.speech_rate)
    if args.voice:
        listener = listener or Listener()

    confirmer = ConsoleConfirmer(speaker)
    log = (lambda msg: None) if args.quiet else (lambda msg: print(f"  -> {msg}", file=sys.stderr))
    ctx = Context.create(config, llm, confirm=confirmer, log=log)
    jarvis = build_jarvis(ctx)

    def handle(request: str) -> int:
        confirmer.new_request()
        try:
            answer = jarvis.run(request)
        except LLMError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"jarvis> {answer}")
        if speaker:
            speaker.say(answer)
        return 0

    def hear() -> str | None:
        listening_cue(config.os_name)
        try:
            wav = listener.record()
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return None
        if wav is None:
            print("  (didn't hear anything)", file=sys.stderr)
            return None
        try:
            text = llm.transcribe(wav).strip()
        except LLMError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return None
        if not text:
            print("  (couldn't make that out)", file=sys.stderr)
            return None
        print(f"you said> {text}")
        return text

    if args.command:
        return handle(args.command)

    print((VOICE_BANNER if args.voice else BANNER) + (" (DRY RUN)" if config.dry_run else ""))
    if speaker:
        speaker.say("Jarvis online.")
    while True:
        try:
            request = input("\nyou> " if not args.voice else "\nyou (Enter = speak)> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not request:
            if not args.voice:
                continue
            request = hear()
            if not request:
                continue
        if request.lower() in ("/quit", "/exit", "quit", "exit", "goodbye jarvis"):
            return 0
        if request == "/reset":
            jarvis.reset()
            print("Conversation cleared.")
            continue
        if request == "/tools":
            for t in jarvis.tools:
                tag = (" (sub-agent)" if t.name.startswith("delegate_to_") else " (sensitive)" if t.sensitive
                       else " (look only)" if t.read_only else "")
                print(f"  {t.name}{tag}: {t.description}")
            continue
        if request == "/log":
            show_log(ctx)
            continue
        try:
            handle(request)
        except KeyboardInterrupt:
            print("\n(interrupted)")


def show_log(ctx: Context, n: int = 20) -> None:
    entries = ctx.actions.tail(n)
    if not entries:
        print(f"No actions logged yet ({ctx.config.log_file}).")
        return
    for e in entries:
        status = "ok" if e["ok"] else "FAILED"
        print(f"  {e['time']}  {e['decision']:<8} {status:<6} {e['agent']}: {describe_action(e['tool'], e['args'])}")
    s = ctx.actions.stats()
    print(f"Total: {s['actions']} actions, {s['declined']} declined by you, {s['failed']} failed. "
          f"Full log: {ctx.config.log_file}")


if __name__ == "__main__":
    raise SystemExit(main())
