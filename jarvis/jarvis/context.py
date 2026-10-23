"""Shared runtime objects handed to every tool factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from jarvis.computer import Computer, DesktopComputer, RecordingComputer
from jarvis.config import Config
from jarvis.executor import Executor, RecordingExecutor
from jarvis.llm import LLM

ConfirmFn = Callable[[str, dict[str, Any]], bool]


def deny_all(name: str, args: dict[str, Any]) -> bool:
    return False


@dataclass
class Context:
    config: Config
    llm: LLM
    executor: Executor
    computer: Computer
    confirm: ConfirmFn = deny_all
    log: Callable[[str], None] = field(default=lambda msg: None)
    sleep: Callable[[float], None] = field(default=None)  # injectable so tests don't wait

    def __post_init__(self) -> None:
        if self.sleep is None:
            import time

            self.sleep = time.sleep

    @classmethod
    def create(cls, config: Config, llm: LLM, **kwargs: Any) -> "Context":
        if config.dry_run:
            kwargs.setdefault("executor", RecordingExecutor())
            kwargs.setdefault("computer", RecordingComputer())
        kwargs.setdefault("executor", Executor())
        kwargs.setdefault("computer", DesktopComputer())
        return cls(config=config, llm=llm, **kwargs)
