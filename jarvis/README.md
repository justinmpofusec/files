# Jarvis

A personal assistant for your Mac that **thinks with Gemini**, **talks and listens**, and **acts on your
computer**. It opens apps and websites, sends WhatsApp and iMessage messages, looks at your screen, uses the
keyboard and mouse, and hands long multi-step jobs to specialised **sub-agents**: a computer operator and a
Blender 3D artist. It **asks your permission before every action** until you decide to trust it with more.

**New here? Follow the step-by-step guide: [docs/SETUP_MAC.md](docs/SETUP_MAC.md).**

```
you (Enter = speak)>
  Listening... (stop talking to finish)
you said> open spotify and text mum on whatsapp that I'm running ten minutes late

  Jarvis wants to open Spotify
  Allow? [y]es / [n]o / [a]ll for this request / or type what to do instead: y
  -> [jarvis] open_app(app_name="Spotify")

  Jarvis wants to send a WhatsApp to mum saying: I'm running ten minutes late
  Allow? [y]es / [n]o / [a]ll for this request / or type what to do instead: y
  -> [jarvis] send_whatsapp(recipient="mum", message="I'm running ten minutes late")
jarvis> Spotify is open and I've told your mum you're ten minutes late.      (spoken aloud)
```

## What's inside

| Part | What it does | Code |
|---|---|---|
| Brain | Gemini reads your request and decides which tools to use, step by step | `jarvis/llm.py`, `jarvis/agent.py` |
| Voice | Press Enter and talk. Gemini transcribes your speech, and replies are spoken with the Mac's `say` voice | `jarvis/voice.py` |
| Basic actions | Open apps, websites and files, search the web, AppleScript (Music, Notes, Reminders...), shell commands | `jarvis/tools/system.py` |
| Messaging | WhatsApp (desktop app or Web), iMessage (Messages app), by contact name | `jarvis/tools/messaging.py` |
| Eyes | Screenshot → Gemini vision → "what's on screen?" / "where is the Send button?" | `jarvis/vision.py` |
| Hands | Mouse clicks, typing, keyboard shortcuts, scrolling | `jarvis/computer.py`, `jarvis/tools/screen.py` |
| Sub-agents | Specialists that run their own look → act → check loop for long tasks | `jarvis/subagents/` |
| Safety | Permission prompts, dry-run, action log, fail-safe | `jarvis/agent.py`, `jarvis/actionlog.py` |

### What is a sub-agent?

A sub-agent is a **second, specialised Jarvis** that the main Jarvis can hand a whole job to.
It gets its own instructions and only the tools for that job, and it works on the task in a loop until it's done.
Then it reports back, and main Jarvis tells you the result.

* **Computer operator** (`delegate_to_computer`): for jobs that need many clicks in an app, e.g. *"in Notes, make
  a note called Shopping with eggs, milk and bread"*. It repeats: **look** at the screen → **do one thing**
  (click / type / shortcut) → **look again** to check it worked → next step.
* **Blender artist** (`delegate_to_blender`): for 3D jobs, e.g. *"make a red sphere on a plane and render it"*.
  It writes Blender Python scripts, runs them in the background, reads any errors, fixes them, saves the file
  and renders an image.

Why have sub-agents? Each one has a short, focused tool list and its own memory, so the main conversation stays
clean and each job is done more reliably. You still approve every action a sub-agent takes.
To add your own specialist (say, a Photoshop or Excel agent), see "Adding a tool or sub-agent" below.

## Permissions: start supervised, loosen later

| `JARVIS_CONFIRM` | Asks before... | Use when |
|---|---|---|
| `always` | everything, even screenshots | you want to see every single step |
| `actions` **(default)** | anything that changes something: clicks, typing, opening apps, messages | starting out |
| `sensitive` | only messages, shell commands, AppleScript and Blender scripts | it has proven itself |
| `never` | nothing: fully autonomous | you completely trust it (not recommended for messaging) |

When asked, answer **y** (yes), **n** or Enter (no), **a** (yes to everything for the rest of this request),
or **type an instruction** like *"use Safari instead"*. Jarvis then declines the action and follows your instruction.

Every action is recorded in `~/.jarvis/actions.jsonl`. Type `/log` to see the last 20 actions and a
summary of how many were declined or failed. That record shows when it's safe to switch to `sensitive`.

Other safety features:
* `--dry-run` simulates everything: no clicks, keys, commands or messages.
* WhatsApp checks the screen before pressing Enter. If it can't confirm the right chat is open, it doesn't send.
* **Fail-safe:** slam the mouse into any screen corner to stop all keyboard and mouse automation immediately.
* Ctrl+C interrupts the current request.

## Quick start (Mac)

```bash
cd jarvis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp contacts.example.json contacts.json          # edit with your real contacts
echo 'GEMINI_API_KEY=your-key-here' > .env      # from https://aistudio.google.com/apikey
jarvis --dry-run                                # rehearse safely
jarvis --voice                                  # the real thing, with voice
```

Grant your terminal app **Accessibility**, **Screen Recording** and **Microphone** in System Settings →
Privacy & Security. The full walkthrough is in [docs/SETUP_MAC.md](docs/SETUP_MAC.md).

## Commands

```bash
jarvis                     # type requests
jarvis --voice             # press Enter and speak; replies are spoken
jarvis --speak             # type requests, hear replies
jarvis -c "open safari"    # one request, then exit
jarvis --dry-run           # pretend mode
jarvis --confirm sensitive # ask less often
```

Inside Jarvis: `/tools` lists tools, `/log` shows recent actions, `/reset` clears the conversation, and `/quit`
exits. In voice mode you can also say "goodbye Jarvis".

## Settings (`.env` file or environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | – | Required. Google AI Studio key. |
| `JARVIS_MODEL` | `gemini-3.5-flash` | Model for thinking, tool use and speech transcription. |
| `JARVIS_VISION_MODEL` | = `JARVIS_MODEL` | Model for screenshots. |
| `JARVIS_CONFIRM` | `actions` | `always`, `actions`, `sensitive` or `never` (see above). |
| `JARVIS_SPEAK` | `false` | Always speak replies. |
| `JARVIS_VOICE` | system voice | Mac voice name, e.g. `Daniel` (list them with `say -v '?'`). |
| `JARVIS_SPEECH_RATE` | `190` | Words per minute. |
| `JARVIS_DRY_RUN` | `false` | Simulate all actions. |
| `JARVIS_MAX_STEPS` | `25` | Tool rounds per request (the computer sub-agent gets at least 40). |
| `JARVIS_CONTACTS` | `contacts.json` | `{"mum": {"phone": "+44...", "imessage": "+44..."}}` |
| `JARVIS_WHATSAPP` | `auto` | `desktop` (WhatsApp app), `web` (WhatsApp Web), `auto` (app on Mac). |
| `JARVIS_BLENDER` | auto-detect | Path to Blender, e.g. `/Applications/Blender.app/Contents/MacOS/Blender`. |
| `JARVIS_LOG_FILE` | `~/.jarvis/actions.jsonl` | Where actions are recorded. |

## Tests

```bash
pytest                          # everything that doesn't need your key (~100 tests, a few seconds)
GEMINI_API_KEY=... pytest -m live   # real Gemini: tool calling, vision and speech transcription
xvfb-run -a pytest              # Linux only: also drives a real (virtual) screen
```

The suite covers:
* the agent loop, every permission mode and the action log;
* every tool's real commands, the voice pipeline (speech detection on real synthesized speech, `say` commands)
  and the Gemini adapter, checked against Google's real SDK types;
* real Blender (build → save → inspect → render), when Blender is installed;
* on a virtual display, the real keyboard, mouse and screenshots driving a live app, including the computer
  sub-agent completing a task end to end.

## Adding a tool or sub-agent

```python
from jarvis.tools.base import tool

@tool("Set the Mac's output volume.", level="0-100")
def set_volume(level: int) -> str:
    ctx.executor.run(["osascript", "-e", f"set volume output volume {int(level)}"])
    return f"Volume set to {level}."
```

Add it to a `build(ctx)` list, e.g. in `jarvis/tools/system.py`. The JSON schema comes from the type hints.
Use `read_only=True` for tools that only look, and `sensitive=True` for high-stakes ones.

A new sub-agent is an `Agent(name, prompt, ToolRegistry().add(...), ctx)`. Expose it with
`agent.as_tool("...")` in `jarvis/assistant.py`; copy `jarvis/subagents/blender.py` as a template.
