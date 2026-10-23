"""Optional live checks against the real Gemini API: GEMINI_API_KEY=... pytest -m live"""

import os

import pytest

from jarvis.llm import GeminiLLM
from jarvis.tools.base import tool

KEY = os.environ.get("GEMINI_API_KEY")  # read at import: the autouse clean_env fixture hides it during tests
pytestmark = [pytest.mark.live, pytest.mark.skipif(not KEY, reason="no GEMINI_API_KEY")]
MODEL = os.environ.get("JARVIS_MODEL", "gemini-3.5-flash")


def test_live_tool_call_round_trip():
    from jarvis.llm import ToolResult

    @tool("Open an application by name.", app_name="Application name")
    def open_app(app_name: str) -> str:
        return f"Opened {app_name}."

    chat = GeminiLLM(KEY, MODEL).chat("You control a computer via tools.", [open_app])
    reply = chat.send("Please open Spotify.")
    assert reply.tool_calls and reply.tool_calls[0].name == "open_app"
    assert "spotify" in reply.tool_calls[0].args["app_name"].lower()
    final = chat.send([ToolResult(reply.tool_calls[0], "Opened Spotify.")])
    assert final.text and not final.tool_calls


def test_live_vision_locate():
    from PIL import Image, ImageDraw

    from jarvis.computer import RecordingComputer, _encode_png
    from jarvis.vision import ScreenVision

    img = Image.new("RGB", (1000, 1000), "white")
    ImageDraw.Draw(img).rectangle([700, 700, 900, 800], fill="blue")

    class Screen(RecordingComputer):
        def screenshot(self):
            return _encode_png(img)

    loc = ScreenVision(Screen(size=(1000, 1000)), GeminiLLM(KEY, MODEL)).locate("the blue rectangle")
    assert loc.found and 650 < loc.x < 950 and 650 < loc.y < 850
