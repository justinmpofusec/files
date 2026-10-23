import json

import pytest

from jarvis.tools.screen import build_control, build_perception
from jarvis.vision import ScreenVision, parse_json


@pytest.mark.parametrize("text", [
    '{"found": true}',
    '```json\n{"found": true}\n```',
    'Sure! Here you go: {"found": true} hope that helps',
])
def test_parse_json_variants(text):
    assert parse_json(text) == {"found": True}


def test_locate_converts_normalized_box_to_screen_coords(make_ctx):
    ctx = make_ctx(vision=[json.dumps({"found": True, "box_2d": [900, 450, 950, 550], "label": "Send"})])
    ctx.computer.size = (1440, 900)  # e.g. a retina Mac's logical size
    loc = ScreenVision(ctx.computer, ctx.llm).locate("send button")
    assert (loc.found, loc.x, loc.y, loc.label) == (True, 720, 832, "Send")
    assert "send button" in ctx.llm.vision_calls[0]


def test_locate_list_wrapped_and_clamped(make_ctx):
    ctx = make_ctx(vision=[json.dumps([{"box_2d": [0, 0, 0, 0]}])])
    loc = ScreenVision(ctx.computer, ctx.llm).locate("corner")
    assert loc.found and (loc.x, loc.y) == (1, 1)  # never the fail-safe corner (0,0)


@pytest.mark.parametrize("answer", [json.dumps({"found": False, "reason": "no such button"}), "garbage", "[]",
                                    json.dumps({"found": True, "box_2d": [1, 2]})])
def test_locate_not_found(make_ctx, answer):
    ctx = make_ctx(vision=[answer])
    assert not ScreenVision(ctx.computer, ctx.llm).locate("x").found


def test_screenshot_sent_is_png_and_downscaled(make_ctx):
    ctx = make_ctx()
    ctx.computer.size = (3840, 2160)
    shot = ctx.computer.screenshot()
    assert shot.png.startswith(b"\x89PNG") and (shot.width, shot.height) == (1600, 900)


def test_perception_tools(make_ctx):
    box = json.dumps({"found": True, "box_2d": [500, 500, 500, 500]})
    ctx = make_ctx(vision=["A browser showing YouTube.", box, box, json.dumps({"found": False, "reason": "hidden"})])
    t = {x.name: x for x in build_perception(ctx)}
    assert t["look_at_screen"](question="What app?") == "A browser showing YouTube."
    assert t["find_on_screen"](description="play") == {"found": True, "x": 960, "y": 540, "label": "play"}
    assert t["click_on"](description="play", double_click=True) == "Clicked 'play' at (960, 540)."
    assert ctx.computer.actions == [("click", 960, 540, "left", 2)]
    assert "Could not find" in t["click_on"](description="ghost")


def test_control_tools(ctx):
    t = {x.name: x for x in build_control(ctx)}
    t["click_at"](x=10, y=20, button="right")
    t["move_mouse"](x=100, y=200)
    t["type_text"](text="hello", press_enter=True)
    t["press_key"](key="ESC")
    t["hotkey"](keys=["Command", "Space"])
    t["scroll"](amount=-3)
    assert ctx.computer.actions == [
        ("click", 10, 20, "right", 1), ("move", 100, 200), ("type", "hello"), ("press", "enter"),
        ("press", "esc"), ("hotkey", "command", "space"), ("scroll", -3),
    ]
    assert t["screen_info"]() == {"width": 1920, "height": 1080, "mouse_x": 100, "mouse_y": 200}
    with pytest.raises(ValueError):
        t["click_at"](x=5000, y=5)
    with pytest.raises(ValueError):
        t["hotkey"](keys=[])


def test_desktop_computer_reports_missing_pyautogui(monkeypatch):
    import sys

    from jarvis.computer import DesktopComputer

    monkeypatch.setitem(sys.modules, "pyautogui", None)  # makes `import pyautogui` raise ImportError
    with pytest.raises(RuntimeError, match="pip install pyautogui"):
        DesktopComputer().screen_size()
