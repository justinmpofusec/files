"""Stage 2: screen perception. Screenshots are sent to a vision model to describe the
screen or to locate UI elements, which are converted back to real mouse coordinates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from jarvis.computer import Computer
from jarvis.llm import LLM

LOCATE_PROMPT = (
    "You are locating a UI element in a screenshot so a program can click it.\n"
    "Element to find: {target}\n"
    "Reply ONLY with JSON: {{\"found\": true, \"box_2d\": [ymin, xmin, ymax, xmax], \"label\": \"what you found\"}} "
    "with coordinates normalized to 0-1000, or {{\"found\": false, \"reason\": \"...\"}} if it is not visible."
)

DESCRIBE_PROMPT = (
    "This is a screenshot of the user's computer screen. {question}\n"
    "Be concise and concrete: name visible apps, windows, buttons and text that matter."
)


def parse_json(text: str) -> Any:
    """Parse a model's JSON answer, tolerating ```json fences or surrounding prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if match:
            return json.loads(match.group(1))
        raise


@dataclass
class Location:
    found: bool
    x: int = 0
    y: int = 0
    label: str = ""
    reason: str = ""


class ScreenVision:
    def __init__(self, computer: Computer, llm: LLM) -> None:
        self.computer = computer
        self.llm = llm

    def describe(self, question: str = "Describe what is on the screen.") -> str:
        shot = self.computer.screenshot()
        return self.llm.vision(shot.png, DESCRIBE_PROMPT.format(question=question))

    def locate(self, target: str) -> Location:
        shot = self.computer.screenshot()
        raw = self.llm.vision(shot.png, LOCATE_PROMPT.format(target=target), json_output=True)
        try:
            data = parse_json(raw)
        except (json.JSONDecodeError, ValueError):
            return Location(False, reason=f"unreadable vision answer: {raw[:200]}")
        if isinstance(data, list):  # some models wrap the object in a list
            data = data[0] if data else {}
        box = data.get("box_2d")
        if not data.get("found", box is not None) or not box or len(box) != 4:
            return Location(False, reason=data.get("reason", "not found"))
        ymin, xmin, ymax, xmax = (float(v) for v in box)
        width, height = self.computer.screen_size()  # mouse coordinates (logical points, handles HiDPI)
        x = round((xmin + xmax) / 2 / 1000 * width)
        y = round((ymin + ymax) / 2 / 1000 * height)
        x, y = min(max(x, 1), width - 2), min(max(y, 1), height - 2)  # stay off fail-safe corners
        return Location(True, x, y, label=data.get("label", target))
