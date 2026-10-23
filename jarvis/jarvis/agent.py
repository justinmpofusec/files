"""The agent loop: send the user's request to the LLM, run the tools it asks for, feed results back."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from jarvis.context import Context
from jarvis.llm import ChatSession, LLMReply, ToolCall, ToolResult
from jarvis.tools.base import Tool, ToolRegistry, coerce_args


@dataclass
class Agent:
    name: str
    system_prompt: str
    tools: ToolRegistry
    ctx: Context
    max_steps: int | None = None
    _session: ChatSession | None = field(default=None, init=False, repr=False)
    transcript: list[tuple[str, Any]] = field(default_factory=list, init=False, repr=False)

    @property
    def session(self) -> ChatSession:
        if self._session is None:
            self._session = self.ctx.llm.chat(self.system_prompt, list(self.tools))
        return self._session

    def reset(self) -> None:
        self._session = None
        self.transcript.clear()

    def run(self, request: str) -> str:
        """Handle one user request, possibly over many tool-call rounds. Conversation memory persists."""
        max_steps = self.max_steps or self.ctx.config.max_steps
        self.transcript.append(("user", request))
        reply: LLMReply = self.session.send(request)
        for _ in range(max_steps):
            if reply.text:
                self.transcript.append(("assistant", reply.text))
            if not reply.tool_calls:
                return reply.text or "Done."
            results = [self.execute(call) for call in reply.tool_calls]
            reply = self.session.send(results)
        return (reply.text + "\n" if reply.text else "") + f"[{self.name}] Stopped after {max_steps} steps."

    def needs_confirmation(self, t: Tool) -> bool:
        mode = self.ctx.config.confirm
        return mode == "always" or (mode == "sensitive" and t.sensitive)

    def execute(self, call: ToolCall) -> ToolResult:
        t = self.tools.get(call.name)
        self.transcript.append(("tool_call", call))
        if t is None:
            result = ToolResult(call, f"unknown tool {call.name!r}", error=True)
        elif self.needs_confirmation(t) and not self.ctx.config.dry_run and not self.ctx.confirm(t.name, call.args):
            result = ToolResult(call, "The user declined this action. Do not retry it; ask what they want instead.",
                                error=True)
        else:
            self.ctx.log(f"[{self.name}] {call.name}({_fmt_args(call.args)})")
            try:
                result = ToolResult(call, t(**coerce_args(t, call.args)))
            except TypeError as exc:
                result = ToolResult(call, f"bad arguments: {exc}", error=True)
            except Exception as exc:  # tools must never crash the assistant
                result = ToolResult(call, f"{type(exc).__name__}: {exc}", error=True)
        self.transcript.append(("tool_result", result))
        return result

    def as_tool(self, description: str) -> Tool:
        """Expose this agent as a single tool another agent can delegate to."""

        def delegate(task: str) -> str:
            self.reset()  # each delegated task starts clean
            return self.run(task)

        return Tool(
            name=f"delegate_to_{self.name}",
            description=description,
            func=delegate,
            parameters={
                "type": "object",
                "properties": {"task": {"type": "string", "description": "Full, self-contained task description."}},
                "required": ["task"],
            },
        )


def _fmt_args(args: dict[str, Any], limit: int = 160) -> str:
    text = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
    return text if len(text) <= limit else text[:limit] + "…"
