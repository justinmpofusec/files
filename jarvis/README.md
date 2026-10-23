# Jarvis

A personal assistant that **thinks with Gemini** and **acts on your computer**: it opens apps and websites,
sends WhatsApp/iMessage messages, looks at your screen, drives the keyboard and mouse, and hands long
multi-step jobs to specialised **sub-agents** (a computer operator and a Blender 3D artist).

```
you> open spotify and text mum that I'm 10 minutes late on whatsapp
  -> [jarvis] open_app(app_name="Spotify")
  -> [jarvis] send_whatsapp(recipient="mum", message="I'm 10 minutes late")
  Jarvis wants to run send_whatsapp: ... Allow? [y/N] y
Spotify is open and I've messaged Mum on WhatsApp.
```

## How it works

| Stage (from the project notes) | Where it lives |
|---|---|
| 1. Core intelligence via an external API (Gemini) with tool calling | `jarvis/llm.py`, `jarvis/agent.py` |
| 1. Basic automation: open apps/URLs/files, shell, WhatsApp, iMessage | `jarvis/tools/system.py`, `jarvis/tools/messaging.py` |
| 2. Screen perception: screenshot → vision model → description / element coordinates | `jarvis/vision.py`, `jarvis/tools/screen.py` |
| 2. Direct control: keyboard, mouse, hotkeys, scrolling (pyautogui + mss) | `jarvis/computer.py`, `jarvis/tools/screen.py` |
| 3. Sub-agents for autonomous multi-step tasks | `jarvis/subagents/computer.py` (any desktop app), `jarvis/subagents/blender.py` (Blender via `bpy`) |

The main agent (`jarvis/assistant.py`) gets every tool plus `delegate_to_computer` and `delegate_to_blender`.
Each sub-agent is itself an agent with its own prompt and tools; it runs its own observe → act → verify loop
and reports back.

Safety built in:
* Sensitive tools (sending messages, shell commands, running Blender scripts) **ask before running**
  (`--confirm always|sensitive|never`).
* `--dry-run` simulates everything: no real clicks, keys, commands or messages.
* WhatsApp sending checks the screen with the vision model before pressing Enter; if it can't confirm the chat is
  ready, it leaves the message typed and does not send it.
* pyautogui fail-safe: slam the mouse into a screen corner to abort any automation.
* iMessage text is passed to AppleScript as arguments, so quotes in a message can't inject script code.

## Setup

Requires Python 3.10+.

```bash
cd jarvis
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp contacts.example.json contacts.json                  # put your real contacts in here
echo 'GEMINI_API_KEY=your-key-here' > .env              # key from https://aistudio.google.com/apikey
```

OS permissions you'll need to grant once:
* **macOS**: System Settings → Privacy & Security → *Accessibility* and *Screen Recording* for your terminal app;
  the first iMessage will ask for permission to control *Messages*.
* **Linux**: an X11 session (Wayland blocks synthetic input/screenshots), plus `sudo apt install python3-tk xclip`.
* **Windows**: nothing extra; run the terminal as the same user who's logged in.

For WhatsApp, install WhatsApp Desktop and sign in (or set `JARVIS_WHATSAPP=web` and keep WhatsApp Web signed in).
For Blender, install it from blender.org; set `JARVIS_BLENDER` if `blender` isn't on your PATH.

## Use

```bash
jarvis                               # interactive; /tools lists tools, /reset clears memory, /quit exits
jarvis -c "open youtube and search for lo-fi music"
jarvis --dry-run -c "text alex on imessage saying hi"    # rehearse without doing anything
python -m jarvis                     # same as `jarvis`
```

Example requests:
* "Open Safari and go to bbc.co.uk"
* "What's on my screen right now?"
* "Send Mum a WhatsApp saying dinner at 7"
* "In the open Notes app, create a new note titled Shopping with eggs, milk and bread" (computer sub-agent)
* "Make a Blender scene with a red sphere on a plane, save it to ~/sphere.blend and render a preview to ~/sphere.png"

## Settings (environment variables or `.env`)

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | – | Required. Google AI Studio key. |
| `JARVIS_MODEL` | `gemini-3.5-flash` | Model for reasoning/tool calls. |
| `JARVIS_VISION_MODEL` | = `JARVIS_MODEL` | Model for screenshots. |
| `JARVIS_CONFIRM` | `sensitive` | `always`, `sensitive` or `never`. |
| `JARVIS_DRY_RUN` | `false` | Simulate all actions. |
| `JARVIS_MAX_STEPS` | `25` | Tool rounds per request (the computer sub-agent gets at least 40). |
| `JARVIS_CONTACTS` | `contacts.json` | Contacts file: `{"mum": {"phone": "+44...", "imessage": "+44..."}}` |
| `JARVIS_WHATSAPP` | `auto` | `desktop` (whatsapp:// app link), `web`, or `auto` (web on Linux). |
| `JARVIS_BLENDER` | `blender` | Path to the Blender executable. |

## Tests

```bash
pytest                                        # unit + integration tests (no API key or screen needed)
xvfb-run -a pytest                            # Linux: also runs the real keyboard/mouse/screen tests
GEMINI_API_KEY=... pytest -m live             # optional: real Gemini tool-call + vision checks
```

The suite covers the agent loop, confirmations, every tool's real commands on macOS/Windows/Linux,
the Gemini adapter against real `google-genai` types, real Blender (scene build → save → inspect → render) when
Blender is installed, and real pyautogui/mss control of a live Tk app under Xvfb, including the computer
sub-agent completing a task end to end.

## Adding a tool or sub-agent

```python
from jarvis.tools.base import tool

@tool("Turn the volume to a level.", sensitive=False, level="0-100")
def set_volume(level: int) -> str:
    ...
    return f"Volume set to {level}."
```

Add it to a `build(ctx)` list (e.g. in `jarvis/tools/system.py`). The JSON schema comes from the type hints.
A new sub-agent is an `Agent(name, prompt, ToolRegistry().add(...), ctx)`; expose it with `agent.as_tool("...")`
in `jarvis/assistant.py` (see `jarvis/subagents/blender.py`).
