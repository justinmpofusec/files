from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from jarvis.actionlog import ActionLog
from jarvis.computer import RecordingComputer
from jarvis.config import Config
from jarvis.context import Context
from jarvis.executor import RecordingExecutor
from jarvis.llm import LLMReply, ScriptedLLM, ToolCall


@dataclass
class Confirmer:
    answer: bool = True
    asked: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __call__(self, name, args):
        self.asked.append((name, args))
        return self.answer


def call(name: str, **args) -> LLMReply:
    return LLMReply(tool_calls=[ToolCall(name, args, id=f"id-{name}")])


def say(text: str) -> LLMReply:
    return LLMReply(text=text)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Isolate tests from the developer's real Jarvis settings and from each other's .env loading."""
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith(("JARVIS_", "GEMINI_", "GOOGLE_API"))}
    env["JARVIS_LOG_FILE"] = str(tmp_path / "actions.jsonl")  # never write to the real ~/.jarvis
    monkeypatch.setattr(os, "environ", env)


@pytest.fixture
def make_ctx(tmp_path):
    def make(os_name="Darwin", replies=None, vision=None, confirm=True, **config_kw) -> Context:
        config_kw.setdefault("contacts_file", tmp_path / "contacts.json")
        config = Config(os_name=os_name, **config_kw)
        return Context(
            config=config,
            llm=ScriptedLLM(replies, vision),
            executor=RecordingExecutor(),
            computer=RecordingComputer(),
            confirm=Confirmer(confirm),
            sleep=lambda s: None,
            actions=ActionLog(tmp_path / "actions.jsonl"),
        )

    return make


@pytest.fixture
def ctx(make_ctx):
    return make_ctx()


def tool_by_name(tools, name):
    return next(t for t in tools if t.name == name)
