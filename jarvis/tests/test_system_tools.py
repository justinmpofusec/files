import urllib.parse

import pytest
from conftest import tool_by_name

from jarvis.executor import CommandResult
from jarvis.tools import system


def tools(ctx):
    return {t.name: t for t in system.build(ctx)}


def test_open_app_macos(make_ctx):
    ctx = make_ctx("Darwin")
    assert tools(ctx)["open_app"](app_name="Spotify") == "Opened Spotify."
    assert ctx.executor.calls == [("run", ["open", "-a", "Spotify"], False)]


def test_open_app_windows(make_ctx):
    ctx = make_ctx("Windows")
    tools(ctx)["open_app"](app_name="notepad")
    assert ctx.executor.calls == [("run", ["cmd", "/c", "start", "", "notepad"], False)]


def test_open_app_linux_uses_path_or_gtk_launch(make_ctx, monkeypatch):
    ctx = make_ctx("Linux")
    monkeypatch.setattr(system.shutil, "which", lambda n: "/usr/bin/firefox" if n == "firefox" else None)
    tools(ctx)["open_app"](app_name="Firefox")
    tools(ctx)["open_app"](app_name="Visual Studio Code")
    assert ctx.executor.calls == [("launch", ["/usr/bin/firefox"]),
                                  ("run", ["gtk-launch", "visual-studio-code"], False)]


def test_open_app_failure_message(make_ctx):
    ctx = make_ctx("Darwin")
    ctx.executor.results["open"] = CommandResult(1, stderr="Unable to find application named 'Nope'")
    assert "Unable to find application" in tools(ctx)["open_app"](app_name="Nope")


def test_open_url_and_search(ctx):
    t = tools(ctx)
    assert t["open_url"](url="example.com") == "Opened https://example.com."
    t["web_search"](query="weather in leeds & york")
    assert ctx.executor.calls[0] == ("open_url", "https://example.com")
    url = ctx.executor.calls[1][1]
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"] == ["weather in leeds & york"]


@pytest.mark.parametrize("os_name,opener", [("Darwin", "open"), ("Windows", "explorer"), ("Linux", "xdg-open")])
def test_open_path(make_ctx, tmp_path, os_name, opener):
    ctx = make_ctx(os_name)
    t = tools(ctx)
    assert "No such file" in t["open_path"](path=str(tmp_path / "missing.txt"))
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    t["open_path"](path=str(f))
    assert ctx.executor.calls == [("launch", [opener, str(f)])]


def test_shell_is_sensitive_and_uses_shell(ctx):
    t = tools(ctx)["run_shell_command"]
    assert t.sensitive
    assert "exit code 0" in t(command="echo hi | wc -c")
    assert ctx.executor.calls == [("run", "echo hi | wc -c", True)]


def test_system_info_list_folder_wait(ctx, tmp_path):
    t = tools(ctx)
    info = t["system_info"]()
    assert info["os"] == "Darwin" and "now" in info
    (tmp_path / "sub").mkdir()
    (tmp_path / "b.txt").write_text("x")
    assert t["list_folder"](path=str(tmp_path)).splitlines()[:2] == ["[dir] sub", "b.txt"]
    assert "Not a folder" in t["list_folder"](path=str(tmp_path / "b.txt"))
    slept = []
    ctx.sleep = slept.append
    assert t["wait"](seconds=99) == "Waited 30s."
    assert slept == [30.0]


def test_real_executor_runs_commands():
    from jarvis.executor import Executor

    ex = Executor()
    res = ex.run(["python3", "-c", "print('hello')"])
    assert res.ok and res.stdout.strip() == "hello"
    assert ex.run(["definitely-not-a-real-binary-xyz"]).returncode == 127
    assert ex.run("exit 3", shell=True).returncode == 3
    assert ex.run(["sleep", "5"], timeout=0.2).returncode == 124


def test_applescript_tool_on_mac_only(make_ctx):
    ctx = make_ctx("Darwin")
    t = tools(ctx)["run_applescript"]
    assert t.sensitive
    assert t(script='tell application "Music" to play') == "[dry-run]"
    assert ctx.executor.calls == [("run", ["osascript", "-e", 'tell application "Music" to play'], False)]
    ctx.executor.results["osascript"] = CommandResult(1, stderr="Music got an error")
    assert t(script="x") == "AppleScript error: Music got an error"
    assert "run_applescript" not in tools(make_ctx("Linux"))
