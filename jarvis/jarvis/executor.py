"""All process/URL side effects go through an Executor so dry-run and tests can intercept them."""

from __future__ import annotations

import subprocess
import webbrowser
from dataclasses import dataclass, field


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def summary(self, limit: int = 4000) -> str:
        text = f"exit code {self.returncode}"
        if self.stdout.strip():
            text += f"\nstdout:\n{self.stdout.strip()[-limit:]}"
        if self.stderr.strip():
            text += f"\nstderr:\n{self.stderr.strip()[-limit:]}"
        return text


class Executor:
    def run(self, args: list[str] | str, *, shell: bool = False, timeout: float = 120) -> CommandResult:
        try:
            proc = subprocess.run(args, shell=shell, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as exc:
            return CommandResult(127, stderr=str(exc))
        except subprocess.TimeoutExpired:
            return CommandResult(124, stderr=f"timed out after {timeout}s")
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)

    def launch(self, args: list[str]) -> CommandResult:
        """Start a program without waiting for it to exit."""
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except (FileNotFoundError, OSError) as exc:
            return CommandResult(127, stderr=str(exc))
        return CommandResult(0)

    def open_url(self, url: str) -> CommandResult:
        return CommandResult(0) if webbrowser.open(url) else CommandResult(1, stderr="no browser available")


@dataclass
class RecordingExecutor(Executor):
    """Records actions instead of performing them. Used for --dry-run and tests."""

    calls: list[tuple] = field(default_factory=list)
    results: dict[str, CommandResult] = field(default_factory=dict)  # keyed by first arg / url prefix

    def _result(self, key: str) -> CommandResult:
        for prefix, result in self.results.items():
            if key.startswith(prefix):
                return result
        return CommandResult(0, stdout="[dry-run]")

    def run(self, args, *, shell=False, timeout=120):
        self.calls.append(("run", args, shell))
        return self._result(args if isinstance(args, str) else args[0])

    def launch(self, args):
        self.calls.append(("launch", args))
        return self._result(args[0])

    def open_url(self, url):
        self.calls.append(("open_url", url))
        return self._result(url)
