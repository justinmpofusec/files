"""Drives a REAL display (run under Xvfb on Linux: `xvfb-run -a pytest -m gui`).
Uses pyautogui + mss exactly as Jarvis does on a desktop."""

import io
import json
import os
import shutil
import subprocess
import time

import pytest

from conftest import call, say

pytestmark = [pytest.mark.gui, pytest.mark.skipif(not os.environ.get("DISPLAY") and os.name != "nt"
                                                  and not os.uname().sysname == "Darwin",
                                                  reason="no display (use xvfb-run)")]


def tk_python():
    for exe in ("python3", "python3.12", "python3.11", "python3.13", "python"):
        path = shutil.which(exe)
        if path and subprocess.run([path, "-c", "import tkinter"], capture_output=True).returncode == 0:
            return path
    pytest.skip("no Python with tkinter available for the GUI target app")


@pytest.fixture
def target_app():
    proc = subprocess.Popen([tk_python(), os.path.join(os.path.dirname(__file__), "gui_target_app.py")],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "READY"
    time.sleep(0.3)
    yield proc
    if proc.poll() is None:
        proc.kill()


def finish(proc):
    from jarvis.computer import DesktopComputer

    DesktopComputer().press("escape")
    out, _ = proc.communicate(timeout=10)
    return json.loads(out.strip().splitlines()[-1])


def test_mouse_and_screen_size():
    from jarvis.computer import DesktopComputer

    c = DesktopComputer()
    w, h = c.screen_size()
    assert w > 100 and h > 100
    c.move(321, 234)
    assert c.mouse_position() == (321, 234)


def test_screenshot_sees_the_app(target_app):
    from PIL import Image

    from jarvis.computer import DesktopComputer

    c = DesktopComputer()
    shot = c.screenshot()
    img = Image.open(io.BytesIO(shot.png)).convert("RGB")
    assert (img.width, img.height) == (shot.width, shot.height)
    scale = img.width / c.screen_size()[0]
    r, g, b = img.getpixel((int(450 * scale), int(270 * scale)))  # red window background
    assert r > 200 and g < 60 and b < 60
    finish(target_app)


def test_keyboard_and_clicks_reach_a_real_app(target_app):
    from jarvis.computer import DesktopComputer

    c = DesktopComputer()
    c.click(300, 135)  # entry
    c.type_text("hello jarvis 123")
    c.press("backspace")
    c.click(170, 220)  # button
    c.click(170, 220)
    c.move(300, 135)  # keep pointer over the app so Escape reaches it without a window manager
    assert finish(target_app) == {"text": "hello jarvis 12", "clicks": 2}


def test_computer_subagent_end_to_end_on_real_screen(target_app, make_ctx):
    """The autonomous loop with the real keyboard/mouse/screen; only the model's decisions are scripted."""
    from jarvis.computer import DesktopComputer
    from jarvis.subagents import computer

    w, h = DesktopComputer().screen_size()

    def to_box(x, y):  # a zero-size box centred on (x, y), in Gemini's 0-1000 [ymin, xmin, ymax, xmax] format
        ny, nx = round(y / h * 1000), round(x / w * 1000)
        return [ny, nx, ny, nx]

    vision = [
        "A red window with an empty text box and a 'Press' button.",
        json.dumps({"found": True, "box_2d": to_box(300, 135), "label": "text box"}),
        json.dumps({"found": True, "box_2d": to_box(170, 220), "label": "Press button"}),
    ]
    replies = [
        call("look_at_screen", question="What is visible?"),
        call("click_on", description="the text box"),
        call("type_text", text="typed by agent"),
        call("click_on", description="the Press button"),
        say("Typed the text and pressed the button."),
    ]
    ctx = make_ctx("Linux", replies=replies, vision=vision)
    ctx.computer = DesktopComputer()
    agent = computer.build(ctx)
    assert agent.run("Type 'typed by agent' in the box and press the button") == "Typed the text and pressed the button."
    ctx.computer.move(300, 135)
    assert finish(target_app) == {"text": "typed by agent", "clicks": 1}
