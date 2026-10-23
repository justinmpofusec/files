"""Builds the main Jarvis agent: direct tools for quick jobs, sub-agents for long multi-step jobs."""

from __future__ import annotations

from jarvis.agent import Agent
from jarvis.context import Context
from jarvis.subagents import blender, computer
from jarvis.tools import messaging, system
from jarvis.tools.base import ToolRegistry
from jarvis.tools.screen import build_control, build_perception

PROMPT = """You are Jarvis, a capable, concise personal assistant running on the user's {os_name} computer.
You can act on the computer through tools. Guidelines:
- For a simple request, call the right tool directly (open an app, open a site, send a message, look at the screen).
- For multi-step work inside desktop apps (filling forms, navigating apps, anything needing many clicks),
  delegate to delegate_to_computer with a complete, self-contained task description.
- For 3D modelling/rendering work, delegate to delegate_to_blender.
- Use contact names with messaging tools; call list_contacts if unsure who someone is. Never invent phone numbers.
- If an action is declined by the user, do not retry it.
- When a tool fails, explain briefly and suggest a fix. Keep final answers short and say what you actually did.
- The user approves your actions one by one. If they decline and say what to do instead, do that.
{extra}"""

MAC_NOTE = ("- This is a Mac: use 'command' in shortcuts, and run_applescript for scriptable apps "
            "(Music, Notes, Reminders, Calendar, Finder, Safari, volume).")
VOICE_NOTE = ("- Your replies are SPOKEN aloud: answer in one to three short, natural sentences. "
              "No markdown, lists, URLs or emoji.")
DRY_RUN_NOTE = "- DRY-RUN MODE: actions are only simulated; tell the user nothing really happened."


def build_jarvis(ctx: Context) -> Agent:
    notes = [MAC_NOTE if ctx.config.os_name == "Darwin" else "",
             VOICE_NOTE if ctx.config.speak else "",
             DRY_RUN_NOTE if ctx.config.dry_run else ""]
    tools = ToolRegistry().add(
        *system.build(ctx),
        *messaging.build(ctx),
        *build_perception(ctx),
        *build_control(ctx),
        computer.build(ctx).as_tool(
            "Hand a multi-step desktop task to the computer-operator sub-agent, which sees the screen and uses "
            "the mouse and keyboard until the task is done. Returns its report."),
        blender.build(ctx).as_tool(
            "Hand a 3D task (create/modify/inspect/render .blend scenes) to the Blender sub-agent. Returns its report."),
    )
    prompt = PROMPT.format(os_name=ctx.config.os_name, extra="\n".join(n for n in notes if n))
    return Agent(name="jarvis", system_prompt=prompt,
                 tools=tools, ctx=ctx)
