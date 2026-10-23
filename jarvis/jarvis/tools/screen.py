"""Stages 2-3: look at the screen and control keyboard & mouse directly."""

from __future__ import annotations

from jarvis.context import Context
from jarvis.tools.base import Tool, tool
from jarvis.vision import ScreenVision


def build_perception(ctx: Context) -> list[Tool]:
    vision = ScreenVision(ctx.computer, ctx.llm)

    @tool("Take a screenshot and ask a vision model about it. Use this to see what is on screen.", read_only=True,
          question="What you want to know, e.g. 'Which app is in front?' or 'Is the file saved?'")
    def look_at_screen(question: str = "Describe what is on the screen.") -> str:
        return vision.describe(question)

    @tool("Find a visible UI element on screen and return its mouse coordinates.", read_only=True,
          description="Describe the element precisely, e.g. 'the blue Send button bottom right'.")
    def find_on_screen(description: str) -> dict:
        loc = vision.locate(description)
        if not loc.found:
            return {"found": False, "reason": loc.reason}
        return {"found": True, "x": loc.x, "y": loc.y, "label": loc.label}

    @tool("Find a UI element on screen by description and click it.",
          description="Describe the element precisely.", button="left, right or middle.",
          double_click="True for a double click.")
    def click_on(description: str, button: str = "left", double_click: bool = False) -> str:
        loc = vision.locate(description)
        if not loc.found:
            return f"Could not find {description!r} on screen ({loc.reason}). Try look_at_screen first."
        ctx.computer.click(loc.x, loc.y, button=button, clicks=2 if double_click else 1)
        return f"Clicked {loc.label!r} at ({loc.x}, {loc.y})."

    return [look_at_screen, find_on_screen, click_on]


def build_control(ctx: Context) -> list[Tool]:
    c = ctx.computer

    def _check(x: int, y: int) -> None:
        width, height = c.screen_size()
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"({x}, {y}) is outside the {width}x{height} screen")

    @tool("Click at exact screen coordinates.", x="Pixels from left.", y="Pixels from top.",
          button="left, right or middle.", clicks="1 = single, 2 = double click.")
    def click_at(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        _check(x, y)
        c.click(x, y, button=button, clicks=clicks)
        return f"Clicked ({x}, {y})."

    @tool("Move the mouse pointer to screen coordinates.", x="Pixels from left.", y="Pixels from top.")
    def move_mouse(x: int, y: int) -> str:
        _check(x, y)
        c.move(x, y)
        return f"Moved mouse to ({x}, {y})."

    @tool("Type text with the keyboard into whatever is focused.", text="Text to type.",
          press_enter="Press Enter afterwards.")
    def type_text(text: str, press_enter: bool = False) -> str:
        c.type_text(text)
        if press_enter:
            c.press("enter")
        return f"Typed {len(text)} characters" + (" and pressed Enter." if press_enter else ".")

    @tool("Press a single key, e.g. enter, esc, tab, space, backspace, up, down, f5.", key="Key name.")
    def press_key(key: str) -> str:
        c.press(key.lower())
        return f"Pressed {key}."

    @tool("Press a keyboard shortcut, e.g. ['command','space'] on macOS or ['ctrl','s'].",
          keys="Keys held together, modifiers first.")
    def hotkey(keys: list[str]) -> str:
        if not keys:
            raise ValueError("keys must not be empty")
        c.hotkey(*[k.lower() for k in keys])
        return f"Pressed {'+'.join(keys)}."

    @tool("Scroll the mouse wheel.", amount="Positive scrolls up, negative scrolls down (clicks of the wheel).")
    def scroll(amount: int) -> str:
        c.scroll(amount)
        return f"Scrolled {amount}."

    @tool("Get the screen size and current mouse position.", read_only=True)
    def screen_info() -> dict:
        width, height = c.screen_size()
        x, y = c.mouse_position()
        return {"width": width, "height": height, "mouse_x": x, "mouse_y": y}

    return [click_at, move_mouse, type_text, press_key, hotkey, scroll, screen_info]
