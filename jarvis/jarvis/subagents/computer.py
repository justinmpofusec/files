"""Computer-use sub-agent: completes multi-step tasks in any desktop app by looking at the
screen and using the keyboard and mouse (observe -> act -> verify loop)."""

from __future__ import annotations

from jarvis.agent import Agent
from jarvis.context import Context
from jarvis.tools import system
from jarvis.tools.base import ToolRegistry
from jarvis.tools.screen import build_control, build_perception

PROMPT = """You are the computer-operator inside Jarvis, operating a {os_name} computer with keyboard and mouse.
Work in a loop: LOOK at the screen (look_at_screen), decide ONE next action, ACT, then LOOK again to verify it worked.
Rules:
- Prefer reliable actions: open_app / open_url to launch things, keyboard shortcuts over hunting for menus,
  click_on with a precise description over guessing coordinates.
- After opening an app or a page, wait 1-3 seconds before looking.
- Never guess: if something unexpected appears (dialog, login, error), describe it and adapt.
- Never enter passwords, payment details, or confirm purchases/deletions; stop and report instead.
- When the task is done (or impossible), stop calling tools and reply with a short report of what happened.
- The user may decline an action or tell you to do something else instead; follow their instruction.{mac}"""

MAC_TIPS = """
- macOS: shortcuts use 'command' (e.g. ['command','space'] opens Spotlight, ['command','tab'] switches apps,
  ['command','w'] closes a window). For scriptable apps (Music, Finder, Notes, Reminders, Calendar, Safari)
  run_applescript is faster and more reliable than clicking."""


def build(ctx: Context) -> Agent:
    helpers = [t for t in system.build(ctx) if t.name in ("open_app", "open_url", "wait", "system_info", "run_applescript")]
    tools = ToolRegistry().add(*build_perception(ctx), *build_control(ctx), *helpers)
    prompt = PROMPT.format(os_name=ctx.config.os_name, mac=MAC_TIPS if ctx.config.os_name == "Darwin" else "")
    return Agent(name="computer", system_prompt=prompt, tools=tools, ctx=ctx,
                 max_steps=max(ctx.config.max_steps, 40))
