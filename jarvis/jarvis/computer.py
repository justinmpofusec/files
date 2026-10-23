"""Keyboard, mouse and screen access.

`DesktopComputer` drives the real machine via pyautogui (input) and mss (screen capture).
Both are imported lazily so Jarvis can start on machines without a display.
`RecordingComputer` records actions for dry-run mode and tests.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Protocol

MAX_SCREENSHOT_WIDTH = 1600  # downscale big/retina screens to keep vision requests small


@dataclass
class Screenshot:
    png: bytes
    width: int  # size of the PNG in pixels
    height: int


class Computer(Protocol):
    def screen_size(self) -> tuple[int, int]: ...
    def screenshot(self) -> Screenshot: ...
    def move(self, x: int, y: int) -> None: ...
    def click(self, x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> None: ...
    def type_text(self, text: str) -> None: ...
    def press(self, key: str) -> None: ...
    def hotkey(self, *keys: str) -> None: ...
    def scroll(self, amount: int) -> None: ...
    def mouse_position(self) -> tuple[int, int]: ...


def _encode_png(image, max_width: int = MAX_SCREENSHOT_WIDTH) -> Screenshot:
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, round(image.height * ratio)))
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return Screenshot(buf.getvalue(), image.width, image.height)


class DesktopComputer:
    """Real keyboard/mouse/screen. Moving the mouse into a screen corner aborts (pyautogui fail-safe)."""

    def __init__(self, type_interval: float = 0.01) -> None:
        self.type_interval = type_interval
        self._gui = None

    @property
    def gui(self):
        if self._gui is None:
            try:
                import pyautogui
            except (ImportError, SystemExit, KeyError) as exc:  # pyautogui calls sys.exit() if tkinter is missing
                raise RuntimeError(
                    "Keyboard/mouse control is unavailable: pyautogui could not start "
                    f"({exc}). Install it with `pip install pyautogui`; on Linux also install "
                    "python3-tk and run inside a graphical (X11) session."
                ) from None

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            self._gui = pyautogui
        return self._gui

    def screen_size(self) -> tuple[int, int]:
        size = self.gui.size()
        return int(size[0]), int(size[1])

    def screenshot(self) -> Screenshot:
        import mss
        from PIL import Image

        with getattr(mss, "MSS", mss.mss)() as sct:
            raw = sct.grab(sct.monitors[1])  # primary monitor
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return _encode_png(image)

    def move(self, x, y):
        self.gui.moveTo(x, y, duration=0.15)

    def click(self, x=None, y=None, button="left", clicks=1):
        self.gui.click(x=x, y=y, button=button, clicks=clicks, interval=0.08)

    def type_text(self, text):
        if text.isascii():
            self.gui.write(text, interval=self.type_interval)
        else:
            # pyautogui.write can't type non-ASCII (emoji, accents): paste via clipboard instead.
            self._paste(text)

    def _paste(self, text: str) -> None:
        import platform
        import shutil
        import subprocess

        system = platform.system()
        if system == "Darwin":
            cmd = ["pbcopy"]
        elif system == "Windows":
            cmd = ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"]
        elif shutil.which("wl-copy"):
            cmd = ["wl-copy"]
        else:
            cmd = ["xclip", "-selection", "clipboard"]
        subprocess.run(cmd, input=text, text=True, check=True, timeout=10)
        self.hotkey("command" if system == "Darwin" else "ctrl", "v")

    def press(self, key):
        self.gui.press(key)

    def hotkey(self, *keys):
        self.gui.hotkey(*keys)

    def scroll(self, amount):
        self.gui.scroll(amount)

    def mouse_position(self):
        pos = self.gui.position()
        return int(pos[0]), int(pos[1])


@dataclass
class RecordingComputer:
    """Pretends to be a 1920x1080 screen and records every action."""

    size: tuple[int, int] = (1920, 1080)
    actions: list[tuple] = field(default_factory=list)
    position: tuple[int, int] = (0, 0)

    def screen_size(self):
        return self.size

    def screenshot(self):
        from PIL import Image

        return _encode_png(Image.new("RGB", self.size, (30, 30, 30)))

    def move(self, x, y):
        self.position = (x, y)
        self.actions.append(("move", x, y))

    def click(self, x=None, y=None, button="left", clicks=1):
        if x is not None and y is not None:
            self.position = (x, y)
        self.actions.append(("click", x, y, button, clicks))

    def type_text(self, text):
        self.actions.append(("type", text))

    def press(self, key):
        self.actions.append(("press", key))

    def hotkey(self, *keys):
        self.actions.append(("hotkey", *keys))

    def scroll(self, amount):
        self.actions.append(("scroll", amount))

    def mouse_position(self):
        return self.position
