import builtins

from conftest import call, say

from jarvis import cli
from jarvis.assistant import build_jarvis
from jarvis.config import Config
from jarvis.context import Context
from jarvis.computer import RecordingComputer
from jarvis.executor import RecordingExecutor
from jarvis.llm import ScriptedLLM

import pytest


def test_jarvis_has_all_stage_tools(ctx):
    names = {t.name for t in build_jarvis(ctx).tools}
    assert {"open_app", "open_url", "send_whatsapp", "send_imessage", "look_at_screen", "click_on",
            "type_text", "hotkey", "delegate_to_computer", "delegate_to_blender"} <= names


def test_dry_run_context_never_touches_machine():
    ctx = Context.create(Config(dry_run=True), ScriptedLLM())
    assert isinstance(ctx.executor, RecordingExecutor) and isinstance(ctx.computer, RecordingComputer)


def test_config_from_env(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text('# comment\nGEMINI_API_KEY="abc"\nJARVIS_DRY_RUN=yes\nJARVIS_CONFIRM=always\n')
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "JARVIS_DRY_RUN", "JARVIS_CONFIRM", "JARVIS_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("JARVIS_MODEL", "gemini-x")
    cfg = Config.from_env(env)
    assert (cfg.api_key, cfg.dry_run, cfg.confirm, cfg.model, cfg.vision_model) == ("abc", True, "always", "gemini-x", "gemini-x")
    with pytest.raises(ValueError):
        Config(confirm="sometimes")


def test_cli_one_shot_end_to_end_dry_run(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    llm = ScriptedLLM([call("open_app", app_name="Spotify"), say("Spotify is open.")])
    assert cli.main(["--dry-run", "-c", "open spotify"], llm=llm) == 0
    out = capsys.readouterr()
    assert "Spotify is open." in out.out
    assert 'open_app(app_name="Spotify")' in out.err


def test_cli_missing_key(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert cli.main(["-c", "hi"]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_cli_repl_commands_and_confirmation(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inputs = iter(["/tools", "", "run ls", "n", "/reset", "/quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    llm = ScriptedLLM([call("run_shell_command", command="ls"), say("You declined, fine.")])
    assert cli.main(["--confirm", "sensitive"], llm=llm) == 0
    out = capsys.readouterr()
    assert "run_shell_command (sensitive)" in out.out and "delegate_to_computer (sub-agent)" in out.out
    assert "You declined, fine." in out.out and "Conversation cleared." in out.out
    assert "Jarvis wants to run the command: ls" in out.err
    assert llm.sent[1][0].error  # declined result went back to the model


def test_console_confirmer_answers():
    answers = iter(["y", "", "no", "a", "use Safari instead"])
    c = cli.ConsoleConfirmer(read=lambda prompt: next(answers))
    assert c("open_app", {"app_name": "Spotify"}) is True
    assert c("open_app", {"app_name": "Spotify"}) is False
    assert c("open_app", {"app_name": "Spotify"}) is False
    assert c("click_on", {"description": "Play"}) is True  # "a" = allow all for this request...
    assert c("type_text", {"text": "anything"}) is True  # ...so this one isn't asked
    c.new_request()
    assert c("open_app", {"app_name": "Chrome"}) == "use Safari instead"  # declined with an instruction

    def eof(prompt):
        raise EOFError
    assert cli.ConsoleConfirmer(read=eof)("x", {}) is False


def test_confirmer_always_shows_details_not_in_summary(capsys):
    c = cli.ConsoleConfirmer(read=lambda p: "n")
    c("run_applescript", {"script": 'tell application "Finder" to delete'})
    c("open_app", {"app_name": "Notes"})
    err = capsys.readouterr().err
    assert 'tell application "Finder" to delete' in err  # short script still shown before approval
    assert "app_name" not in err  # already in "open Notes"


def test_confirmer_speaks_question():
    spoken = []

    class FakeSpeaker:
        def say(self, text):
            spoken.append(text)

    cli.ConsoleConfirmer(FakeSpeaker(), read=lambda p: "y")("send_whatsapp", {"recipient": "mum", "message": "hi"})
    assert spoken == ["May I send a WhatsApp to mum saying: hi?"]


def test_describe_action():
    assert cli.describe_action("hotkey", {"keys": ["command", "space"]}) == "press command+space"
    assert cli.describe_action("open_app", {}) == "open app"  # missing args fall back to the tool name
    assert cli.describe_action("mystery_tool", {"a": 1}) == "mystery tool"
    assert cli.describe_action("type_text", {"text": "Shopping\neggs\n\nmilk"}) == "type: Shopping / eggs / milk"


def test_module_entry_point():
    import subprocess
    import sys

    res = subprocess.run([sys.executable, "-m", "jarvis", "--help"], capture_output=True, text=True)
    assert res.returncode == 0 and "--dry-run" in res.stdout


def test_mac_and_voice_prompts(make_ctx):
    from jarvis.subagents import computer

    ctx = make_ctx("Darwin", speak=True)
    jarvis = build_jarvis(ctx)
    assert "run_applescript" in {t.name for t in jarvis.tools}
    assert "This is a Mac" in jarvis.system_prompt and "SPOKEN aloud" in jarvis.system_prompt
    assert "Spotlight" in computer.build(ctx).system_prompt
    plain = build_jarvis(make_ctx("Linux"))
    assert "Mac" not in plain.system_prompt and "SPOKEN" not in plain.system_prompt


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)
        return True


class FakeListener:
    def __init__(self, recordings):
        self.recordings = list(recordings)

    def record(self):
        return self.recordings.pop(0)


def test_voice_conversation(capsys, tmp_path, monkeypatch):
    """Enter -> speak -> transcribed -> Jarvis acts (after permission) -> reply spoken."""
    from jarvis.voice import to_wav

    monkeypatch.chdir(tmp_path)
    inputs = iter(["", "y", "", "/quit"])  # speak, approve, speak (silence), quit
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    llm = ScriptedLLM([call("open_app", app_name="Spotify"), say("Spotify is open, sir.")],
                      transcripts=["open spotify"])
    speaker = FakeSpeaker()
    listener = FakeListener([to_wav(b"\x01\x00" * 100, 16000), None])
    assert cli.main(["--voice", "--confirm", "actions"], llm=llm, listener=listener, speaker=speaker) == 0
    out = capsys.readouterr()
    assert "you said> open spotify" in out.out and "jarvis> Spotify is open, sir." in out.out
    assert "didn't hear anything" in out.err
    assert speaker.said == ["Jarvis online.", "May I open Spotify?", "Spotify is open, sir."]
    assert llm.sent[0] == "open spotify" and len(llm.audio) == 1
    assert "SPOKEN aloud" in llm.sessions[0].system_prompt


def test_log_command(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inputs = iter(["/log", "open notes", "n", "/log", "/quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    llm = ScriptedLLM([call("open_app", app_name="Notes"), say("OK, I won't.")])
    assert cli.main([], llm=llm) == 0
    out = capsys.readouterr().out
    assert "No actions logged yet" in out
    assert "declined FAILED jarvis: open Notes" in out and "1 declined by you" in out
