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
    assert "run_shell_command (asks first)" in out.out
    assert "You declined, fine." in out.out and "Conversation cleared." in out.out
    assert "Jarvis wants to run run_shell_command" in out.err
    assert llm.sent[1][0].error  # declined result went back to the model


def test_console_confirm(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda p="": "y")
    assert cli.console_confirm("x", {"a": 1})
    def eof(p=""):
        raise EOFError
    monkeypatch.setattr(builtins, "input", eof)
    assert not cli.console_confirm("x", {})


def test_module_entry_point():
    import subprocess
    import sys

    res = subprocess.run([sys.executable, "-m", "jarvis", "--help"], capture_output=True, text=True)
    assert res.returncode == 0 and "--dry-run" in res.stdout
