"""Stage 1: opening apps / URLs / files, running commands, basic system info."""

from __future__ import annotations

import datetime as _dt
import platform
import shutil
import urllib.parse
from pathlib import Path

from jarvis.context import Context
from jarvis.tools.base import Tool, tool


def build(ctx: Context) -> list[Tool]:
    os_name = ctx.config.os_name

    @tool("Open (launch) an application by name, e.g. 'Spotify', 'Safari', 'Blender', 'Calculator'.",
          app_name="Application name as the operating system knows it.")
    def open_app(app_name: str) -> str:
        if os_name == "Darwin":
            result = ctx.executor.run(["open", "-a", app_name])
        elif os_name == "Windows":
            # `start` resolves Start-menu/App-Paths names; the empty "" is the window title argument.
            result = ctx.executor.run(["cmd", "/c", "start", "", app_name])
        else:
            exe = shutil.which(app_name) or shutil.which(app_name.lower()) or shutil.which(app_name.lower().replace(" ", "-"))
            if exe:
                result = ctx.executor.launch([exe])
            else:
                desktop_id = app_name.lower().replace(" ", "-")
                result = ctx.executor.run(["gtk-launch", desktop_id])
        if not result.ok:
            return f"Could not open {app_name}: {result.stderr.strip() or result.summary()}"
        return f"Opened {app_name}."

    @tool("Open a website URL in the default browser.", url="Full URL, e.g. https://example.com")
    def open_url(url: str) -> str:
        if "://" not in url:
            url = "https://" + url
        result = ctx.executor.open_url(url)
        return f"Opened {url}." if result.ok else f"Could not open {url}: {result.stderr}"

    @tool("Search the web in the default browser.", query="What to search for.")
    def web_search(query: str) -> str:
        return open_url(url="https://www.google.com/search?q=" + urllib.parse.quote_plus(query))

    @tool("Open a file or folder with its default application.", path="Absolute path or path relative to home (~).")
    def open_path(path: str) -> str:
        target = Path(path).expanduser()
        if not target.exists():
            return f"No such file or folder: {target}"
        if os_name == "Darwin":
            cmd = ["open", str(target)]
        elif os_name == "Windows":
            cmd = ["explorer", str(target)]
        else:
            cmd = ["xdg-open", str(target)]
        result = ctx.executor.launch(cmd)
        return f"Opened {target}." if result.ok else f"Could not open {target}: {result.stderr}"

    @tool("Run a shell command on this computer and return its output. Use only when no other tool fits.",
          sensitive=True, command="The shell command line.", timeout_seconds="Max run time, default 60.")
    def run_shell_command(command: str, timeout_seconds: int = 60) -> str:
        return ctx.executor.run(command, shell=True, timeout=timeout_seconds).summary()

    @tool("macOS only: run an AppleScript to control Mac apps directly (Music, Finder, Notes, Reminders, Calendar, "
          "Safari, system volume...). Prefer this over clicking when an app is scriptable.", sensitive=True,
          script="The AppleScript source, e.g. 'tell application \"Music\" to play'.")
    def run_applescript(script: str) -> str:
        if os_name != "Darwin":
            return "AppleScript only works on macOS."
        result = ctx.executor.run(["osascript", "-e", script], timeout=60)
        if not result.ok:
            return f"AppleScript error: {result.stderr.strip()}"
        return result.stdout.strip() or "Done."

    @tool("Get current date/time and basic information about this computer.", read_only=True)
    def system_info() -> dict:
        return {
            "now": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "os": os_name,
            "os_version": platform.version(),
            "machine": platform.machine(),
            "home": str(Path.home()),
            "dry_run": ctx.config.dry_run,
        }

    @tool("List files in a folder.", read_only=True, path="Folder path, default home (~).")
    def list_folder(path: str = "~") -> str:
        folder = Path(path).expanduser()
        if not folder.is_dir():
            return f"Not a folder: {folder}"
        entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]
        return "\n".join(f"{'[dir] ' if p.is_dir() else ''}{p.name}" for p in entries) or "(empty)"

    @tool("Wait for a number of seconds (e.g. for an app to finish loading).", read_only=True, seconds="1-30 seconds.")
    def wait(seconds: float) -> str:
        seconds = max(0.0, min(float(seconds), 30.0))
        ctx.sleep(seconds)
        return f"Waited {seconds:g}s."

    tools = [open_app, open_url, web_search, open_path, run_shell_command, system_info, list_folder, wait]
    if os_name == "Darwin":
        tools.append(run_applescript)
    return tools
