# Jarvis on your Mac: step-by-step guide

This takes about 20 minutes the first time. Everything happens in the **Terminal** app
(press ⌘+Space, type "Terminal", press Enter). Type or paste each command, then press Enter.

---

## Part A: Fix GitHub so the code can reach your repository

Right now the code exists only in the Claude session, because Claude was refused access to
`justinmpofusec/files` (error 403). Fix it once:

1. **Install the Claude GitHub App on the repository**
   1. Open https://github.com/apps/claude/installations/select_target while signed in to GitHub as `justinmpofusec`.
   2. Pick your account (`justinmpofusec`).
   3. Choose **Only select repositories** → select **files** (or choose **All repositories**).
   4. Click **Install** (or **Save** if it's already installed). Approve the permissions it asks for.
   5. If the repository belongs to an *organization* rather than your personal account, an owner of that
      organization must do this step, or approve your install request.
2. **Connect GitHub to Claude**
   1. Open https://claude.ai/connect-github (or claude.ai → Settings → Connectors → GitHub → Connect).
   2. Sign in and authorise. If GitHub is already listed, choose **Disconnect** and then connect again.
3. **Tell Claude "push it"** in the same session. Claude pushes the branch
   `claude/prompt-understanding-testing-db4ghc`.
4. Check it worked: open https://github.com/justinmpofusec/files/tree/claude/prompt-understanding-testing-db4ghc.
   You should see a `jarvis` folder.
5. Optional: on GitHub, open a Pull Request from that branch into `main` and merge it, so Jarvis is on your main branch.

If the session has ended before you fix this, start a new Claude Code session with the `files` repository
selected, and upload the `jarvis-project.zip` Claude sent you.

---

## Part B: Install what Jarvis needs

### 1. Python 3.10 or newer
Check what you have:
```bash
python3 --version
```
If it says 3.9 or lower, or "command not found", install Python 3.12 from https://www.python.org/downloads/macos/
(download the macOS installer and double-click it), then **close and reopen Terminal**.

### 2. Get the Jarvis code
```bash
cd ~
git clone https://github.com/justinmpofusec/files.git
cd files
git checkout claude/prompt-understanding-testing-db4ghc     # skip this line if you merged into main
cd jarvis
```
(If `git` asks to install the "command line developer tools", click **Install**, wait, then run the commands again.)
Alternatively, unzip `jarvis-project.zip` and `cd` into its `jarvis` folder.

### 3. Create a private Python environment and install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```
Your prompt now starts with `(.venv)`. **Every time you open a new Terminal to use Jarvis**, first run:
```bash
cd ~/files/jarvis && source .venv/bin/activate
```

### 4. Get a Gemini API key
1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key** and copy it.
3. Save it for Jarvis (replace `PASTE-KEY-HERE`):
```bash
echo 'GEMINI_API_KEY=PASTE-KEY-HERE' > .env
```
Keep this key secret. The `.env` file is already excluded from git, so it won't be uploaded.

### 5. Add your contacts
```bash
cp contacts.example.json contacts.json
open -e contacts.json
```
Edit it in TextEdit. Use full international numbers (`+44...`, `+1...`). For iMessage you can use a phone number
or an Apple ID email:
```json
{
  "mum":  {"phone": "+447700900123", "imessage": "+447700900123"},
  "alex": {"phone": "+15551234567",  "imessage": "alex@icloud.com"}
}
```
Save and close.

### 6. Give your Mac's permissions (important)
Open **System Settings → Privacy & Security** and add **Terminal** (or iTerm, if that's what you use) under each of:

| Setting | Why |
|---|---|
| **Accessibility** | so Jarvis can click and type |
| **Screen & System Audio Recording** (or "Screen Recording") | so Jarvis can see the screen |
| **Microphone** | so Jarvis can hear you (macOS also asks the first time you speak) |

Use the **+** button, then go to Applications → Utilities → Terminal and switch it on.
**Then quit Terminal completely (⌘+Q) and reopen it.** Permissions only apply after a restart.
The first time Jarvis sends an iMessage, macOS asks "Terminal wants to control Messages". Click **OK**.

### 7. Apps Jarvis uses
* **WhatsApp:** install WhatsApp Desktop from the App Store and sign in (scan the QR code with your phone).
* **iMessage:** open Messages and make sure you're signed in with your Apple ID.
* **Blender (optional):** install it from https://www.blender.org/download/ into Applications. Jarvis finds it automatically.

---

## Part C: Check everything works

### 1. Run the tests (no key needed, a few seconds)
```bash
pytest
```
You should see roughly `95 passed, 11 skipped` and no failures. (Skipped tests need your key, Linux, or the
real-screen test below.) You'll hear "Jarvis test." spoken once; that's the voice test.

Optional, and a great permissions check: run the **real screen** tests. They open a small red window, then move
your mouse, click and type into it. Don't touch the mouse for about 10 seconds:
```bash
JARVIS_GUI_TESTS=1 pytest -m gui
```
If they fail with clicks or typing not arriving, the Accessibility or Screen Recording permission from step B6
is missing. (They need the python.org Python, which includes `tkinter`.)

### 2. Test against the real Gemini (uses your key; costs a fraction of a penny)
```bash
set -a; source .env; set +a
pytest -m live
```
All three should pass: tool calling, screen vision and speech transcription.
If one fails with "model not found", see Troubleshooting.

### 3. Hear the voice
```bash
say -v '?' | head -40          # list voices
say -v Daniel "Good evening. Jarvis online."
echo 'JARVIS_VOICE=Daniel' >> .env     # pick the one you like
```

### 4. Rehearse in dry-run (nothing really happens)
```bash
jarvis --dry-run
```
Try `open spotify` and `send mum a whatsapp saying hello`. Jarvis shows what it *would* do. Type `/quit` to leave.

---

## Part D: Using Jarvis

### Start it
```bash
jarvis --voice      # talk to it
jarvis              # type to it
```

### Talking
1. Press **Enter** (you'll hear a "tink"), then speak naturally.
2. Stop talking. After about a second of silence it stops listening, and shows `you said> ...`.
3. You can also type instead of pressing Enter on an empty line.
4. Say "goodbye Jarvis" or type `/quit` to exit.

### Approving actions
Before Jarvis does anything, it asks (and in voice mode, says "May I ...?"):
```
  Jarvis wants to open Spotify
  Allow? [y]es / [n]o / [a]ll for this request / or type what to do instead:
```
* `y`: do it
* `n` or Enter: don't
* `a`: yes to all steps of *this* request (handy for long tasks like the computer operator)
* or type something like `use Safari instead`. Jarvis skips the action and follows your instruction.

Looking at the screen never needs approval; it only looks.

### Things to try
* "Open Safari and go to bbc.co.uk"
* "What's on my screen?"
* "Play music in the Music app" (uses AppleScript)
* "Send Alex an iMessage saying I'll call later"
* "WhatsApp mum that dinner's at 7"
* "In Notes, create a note called Shopping with eggs, milk and bread" (computer operator sub-agent)
* "Make a Blender scene with a red sphere on a plane, save it to my Desktop as sphere.blend and render a preview"
  (Blender sub-agent)

### Reviewing how well it behaves
Type `/log` inside Jarvis:
```
  2026-10-23T18:01:12+01:00  approved ok     jarvis: open Spotify
  2026-10-23T18:01:20+01:00  approved ok     jarvis: send a WhatsApp to mum saying: hi
  2026-10-23T18:03:02+01:00  declined FAILED computer: click the Delete button
Total: 3 actions, 1 declined by you, 1 failed.
```
The full history is in `~/.jarvis/actions.jsonl`.

### Giving it more freedom later
Once it has handled a good number of tasks well (few declines and failures in `/log`), relax the permissions
in `.env`:
```bash
echo 'JARVIS_CONFIRM=sensitive' >> .env   # stop asking for clicks/typing; still ask for messages & scripts
# later, only if you're fully comfortable:
# echo 'JARVIS_CONFIRM=never' >> .env
```
The last value in `.env` wins. Remove the line to go back to the default (`actions`).
**Emergency stop:** slam the mouse into a screen corner (stops all clicks and typing) or press Ctrl+C.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `jarvis: command not found` | Run `cd ~/files/jarvis && source .venv/bin/activate` first. |
| `No Gemini API key` | Check `.env` is in the `jarvis` folder and contains `GEMINI_API_KEY=...`. |
| `API key not valid` | Copy the key again from https://aistudio.google.com/apikey. |
| `model ... not found` | Google renamed a model. Find a current one at https://ai.google.dev/gemini-api/docs/models, then `echo 'JARVIS_MODEL=that-model-id' >> .env`. |
| Clicks/typing do nothing | Accessibility permission is missing for Terminal. Add it, then quit and reopen Terminal. |
| Screenshots are black or show only the wallpaper | Screen Recording permission is missing. Add it, then quit and reopen Terminal. |
| "didn't hear anything" | Microphone permission is missing, or the wrong input device is set (System Settings → Sound → Input). |
| Clicks land in the wrong place | Make sure the app is on your main display; Jarvis only supports the primary monitor. |
| WhatsApp message typed but not sent | That's the safety check: Jarvis couldn't confirm the chat was open. Press Enter yourself, or make sure WhatsApp is signed in and on screen. |
| iMessage fails | Open Messages, check you're signed in, and allow "Terminal wants to control Messages". |
| Mouse stopped mid-task with `FailSafeException` | You moved the mouse into a corner, so the fail-safe stopped it. Just ask again. |
