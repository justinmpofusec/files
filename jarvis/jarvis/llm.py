"""LLM backends. The agent only depends on the small `LLM` / `ChatSession` interface,
so Gemini can be swapped for another provider (or a scripted fake in tests)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from jarvis.tools.base import Tool


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass
class ToolResult:
    call: ToolCall
    output: Any
    error: bool = False

    def as_response(self) -> dict[str, Any]:
        if self.error:
            return {"error": str(self.output)}
        if isinstance(self.output, dict):
            return self.output
        return {"result": self.output if isinstance(self.output, (str, int, float, bool, list)) else str(self.output)}


@dataclass
class LLMReply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ChatSession(Protocol):
    def send(self, message: str | list[ToolResult]) -> LLMReply: ...


class LLM(Protocol):
    def chat(self, system_prompt: str, tools: list[Tool]) -> ChatSession: ...
    def vision(self, image_png: bytes, prompt: str, *, json_output: bool = False) -> str: ...
    def transcribe(self, wav: bytes) -> str: ...


TRANSCRIBE_PROMPT = ("Transcribe the speech in this recording exactly, in its original language. Reply with only the "
                     "spoken words. If there is no intelligible speech, reply with an empty string.")


class LLMError(RuntimeError):
    pass


# ---------------------------------------------------------------- Gemini

_RETRY_CODES = {429, 500, 502, 503, 504}


class GeminiLLM:
    def __init__(self, api_key: str | None, model: str, vision_model: str | None = None, client: Any = None,
                 retries: int = 3, retry_delay: float = 2.0) -> None:
        if client is None:
            if not api_key:
                raise LLMError("No Gemini API key. Set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey).")
            from google import genai

            client = genai.Client(api_key=api_key)
        self.client = client
        self.model = model
        self.vision_model = vision_model or model
        self.retries = retries
        self.retry_delay = retry_delay

    def generate(self, **kwargs: Any) -> Any:
        from google.genai import errors

        for attempt in range(self.retries + 1):
            try:
                return self.client.models.generate_content(**kwargs)
            except errors.APIError as exc:
                if getattr(exc, "code", None) in _RETRY_CODES and attempt < self.retries:
                    time.sleep(self.retry_delay * 2**attempt)
                    continue
                detail = getattr(exc, "message", None) or str(exc)
                raise LLMError(f"Gemini API error {getattr(exc, 'code', '')}: {detail}") from exc
        raise AssertionError("unreachable")

    def chat(self, system_prompt: str, tools: list[Tool]) -> "GeminiChat":
        return GeminiChat(self, system_prompt, tools)

    def vision(self, image_png: bytes, prompt: str, *, json_output: bool = False) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(response_mime_type="application/json") if json_output else None
        response = self.generate(
            model=self.vision_model,
            contents=[types.Part.from_bytes(data=image_png, mime_type="image/png"), prompt],
            config=config,
        )
        return response.text or ""

    def transcribe(self, wav: bytes) -> str:
        from google.genai import types

        response = self.generate(
            model=self.model,
            contents=[types.Part.from_bytes(data=wav, mime_type="audio/wav"), TRANSCRIBE_PROMPT],
        )
        return (response.text or "").strip().strip('"')


class GeminiChat:
    def __init__(self, llm: GeminiLLM, system_prompt: str, tools: list[Tool]) -> None:
        from google.genai import types

        self.llm = llm
        self.history: list[Any] = []
        declarations = [
            types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
            for t in tools
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def send(self, message: str | list[ToolResult]) -> LLMReply:
        from google.genai import types

        if isinstance(message, str):
            content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        else:
            parts = []
            for r in message:
                part = types.Part.from_function_response(name=r.call.name, response=r.as_response())
                if r.call.id:
                    part.function_response.id = r.call.id
                parts.append(part)
            content = types.Content(role="user", parts=parts)
        self.history.append(content)

        response = self.llm.generate(model=self.llm.model, contents=self.history, config=self.config)
        candidates = response.candidates or []
        if not candidates or candidates[0].content is None:
            self.history.pop()  # keep history valid so the user can retry
            reason = getattr(response.prompt_feedback, "block_reason", None) if response.prompt_feedback else None
            raise LLMError(f"Gemini returned no answer (block reason: {reason or 'unknown'})")

        model_content = candidates[0].content
        if not model_content.role:
            model_content.role = "model"
        self.history.append(model_content)  # kept verbatim so Gemini 3 thought signatures are preserved

        texts, calls = [], []
        for part in model_content.parts or []:
            if part.function_call is not None:
                fc = part.function_call
                calls.append(ToolCall(name=fc.name, args=dict(fc.args or {}), id=fc.id))
            elif part.text and not part.thought:
                texts.append(part.text)
        return LLMReply(text="".join(texts).strip(), tool_calls=calls)


# ---------------------------------------------------------------- scripted fake (tests / offline demos)


class ScriptedLLM:
    """Replays canned replies. Each item is an LLMReply, or a callable(message) -> LLMReply."""

    def __init__(self, replies: list[Any] | None = None, vision_replies: list[str] | None = None,
                 transcripts: list[str] | None = None) -> None:
        self.replies = list(replies or [])
        self.transcripts = list(transcripts or [])
        self.audio: list[bytes] = []
        self.vision_replies = list(vision_replies or [])
        self.sent: list[Any] = []
        self.vision_calls: list[str] = []
        self.sessions: list["ScriptedChat"] = []

    def chat(self, system_prompt: str, tools: list[Tool]) -> "ScriptedChat":
        session = ScriptedChat(self, system_prompt, [t.name for t in tools])
        self.sessions.append(session)
        return session

    def vision(self, image_png: bytes, prompt: str, *, json_output: bool = False) -> str:
        assert image_png.startswith(b"\x89PNG"), "vision expects PNG bytes"
        self.vision_calls.append(prompt)
        if not self.vision_replies:
            return json.dumps({"found": False}) if json_output else "An empty desktop."
        return self.vision_replies.pop(0)

    def transcribe(self, wav: bytes) -> str:
        assert wav.startswith(b"RIFF"), "transcribe expects WAV bytes"
        self.audio.append(wav)
        return self.transcripts.pop(0) if self.transcripts else ""


@dataclass
class ScriptedChat:
    llm: ScriptedLLM
    system_prompt: str
    tool_names: list[str]

    def send(self, message):
        self.llm.sent.append(message)
        if not self.llm.replies:
            return LLMReply(text="(no more scripted replies)")
        reply = self.llm.replies.pop(0)
        return reply(message) if callable(reply) else reply
