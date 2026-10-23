"""Append-only record of every action Jarvis takes, so you can review its behaviour before trusting it
with less confirmation. One JSON object per line in ~/.jarvis/actions.jsonl."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any


class ActionLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    def record(self, *, agent: str, tool: str, args: dict[str, Any], decision: str, result: Any, error: bool) -> None:
        if self.path is None:
            return
        entry = {
            "time": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "agent": agent,
            "tool": tool,
            "args": args,
            "decision": decision,  # auto | approved | declined | dry-run
            "ok": not error,
            "result": str(result)[:500],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass  # logging must never break the assistant

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        if self.path is None or not self.path.is_file():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(line) for line in lines if line.strip()]

    def stats(self) -> dict[str, int]:
        entries = self.tail(10**9)
        return {
            "actions": len(entries),
            "declined": sum(e["decision"] == "declined" for e in entries),
            "failed": sum(not e["ok"] for e in entries),
        }
