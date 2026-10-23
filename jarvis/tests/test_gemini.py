"""GeminiLLM against a fake client that returns real google-genai response objects,
so request building and response parsing are checked against the actual SDK types."""

import pytest
from google.genai import errors, types

from jarvis.llm import GeminiLLM, LLMError, ToolCall, ToolResult
from jarvis.tools.base import tool


@tool("Open an app.", app_name="name")
def open_app(app_name: str) -> str:
    return "ok"


def response(*parts, role="model"):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role=role, parts=list(parts)))])


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def generate_content(self, **kwargs):
        # snapshot contents: the chat mutates its history list after the call
        self.requests.append({**kwargs, "contents": list(kwargs["contents"])})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def make(responses, **kw):
    client = FakeClient(responses)
    return GeminiLLM(None, "gemini-test", client=client, retry_delay=0, **kw), client.models


def test_requires_api_key():
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiLLM(None, "m")


def test_real_client_constructs_with_key():
    llm = GeminiLLM("fake-key", "m")
    assert llm.client.models is not None


def test_function_call_round_trip():
    fc = types.Part(function_call=types.FunctionCall(name="open_app", args={"app_name": "Spotify"}, id="call-1"),
                    thought_signature=b"sig")
    llm, models = make([
        response(types.Part(text="thinking...", thought=True), fc),
        response(types.Part.from_text(text="Opened Spotify.")),
    ])
    chat = llm.chat("You are Jarvis.", [open_app])
    reply = chat.send("open spotify")
    assert reply.text == ""  # thought text is not shown to the user
    assert reply.tool_calls == [ToolCall("open_app", {"app_name": "Spotify"}, "call-1")]

    first = models.requests[0]
    assert first["model"] == "gemini-test"
    cfg = first["config"]
    assert cfg.system_instruction == "You are Jarvis."
    decl = cfg.tools[0].function_declarations[0]
    assert decl.name == "open_app" and decl.parameters_json_schema["required"] == ["app_name"]
    assert cfg.automatic_function_calling.disable is True

    reply = chat.send([ToolResult(reply.tool_calls[0], "Opened Spotify.")])
    assert reply.text == "Opened Spotify." and reply.tool_calls == []
    contents = models.requests[1]["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[1].parts[1].thought_signature == b"sig"  # preserved for Gemini 3
    fr = contents[2].parts[0].function_response
    assert (fr.name, fr.id, fr.response) == ("open_app", "call-1", {"result": "Opened Spotify."})
    # the whole request must serialize the way the SDK will send it
    types.GenerateContentConfig.model_validate(cfg.model_dump())
    for c in contents:
        types.Content.model_validate(c.model_dump())


def test_error_result_and_dict_result():
    llm, models = make([response(types.Part.from_text(text="ok"))])
    chat = llm.chat("s", [])
    assert models.requests == []
    chat.send([ToolResult(ToolCall("a"), "boom", error=True), ToolResult(ToolCall("b"), {"x": 1})])
    parts = models.requests[0]["contents"][0].parts
    assert parts[0].function_response.response == {"error": "boom"}
    assert parts[1].function_response.response == {"x": 1}
    assert models.requests[0]["config"].tools is None


def test_retries_transient_errors_then_raises():
    busy = errors.ServerError(503, {"error": {"message": "overloaded"}})
    llm, models = make([busy, response(types.Part.from_text(text="hi"))])
    assert llm.chat("s", []).send("hello").text == "hi"
    assert len(models.requests) == 2

    llm, _ = make([errors.ClientError(400, {"error": {"message": "bad key"}})])
    with pytest.raises(LLMError, match="bad key"):
        llm.chat("s", []).send("hello")

    llm, models = make([busy] * 4, retries=3)
    with pytest.raises(LLMError):
        llm.chat("s", []).send("x")
    assert len(models.requests) == 4


def test_blocked_response_raises_and_keeps_history_valid():
    blocked = types.GenerateContentResponse(candidates=[],
                                            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY"))
    llm, models = make([blocked, response(types.Part.from_text(text="fine"))])
    chat = llm.chat("s", [])
    with pytest.raises(LLMError, match="SAFETY"):
        chat.send("bad")
    assert chat.send("good").text == "fine"
    assert [c.parts[0].text for c in models.requests[1]["contents"]] == ["good"]


def test_vision_sends_image_and_json_mode():
    llm, models = make([response(types.Part.from_text(text='{"found": false}'))])
    assert llm.vision(b"\x89PNGdata", "find it", json_output=True) == '{"found": false}'
    req = models.requests[0]
    assert req["contents"][0].inline_data.mime_type == "image/png"
    assert req["contents"][0].inline_data.data == b"\x89PNGdata"
    assert req["contents"][1] == "find it"
    assert req["config"].response_mime_type == "application/json"


def test_transcribe_sends_wav_audio():
    llm, models = make([response(types.Part.from_text(text='"open spotify"\n'))])
    assert llm.transcribe(b"RIFFfakewav") == "open spotify"
    req = models.requests[0]
    assert req["contents"][0].inline_data.mime_type == "audio/wav"
    assert "Transcribe" in req["contents"][1]
