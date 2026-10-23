import json
import urllib.parse

import pytest

from jarvis.tools import messaging
from jarvis.tools.messaging import normalize_phone

READY = json.dumps({"ready": True, "reason": "chat open"})
NOT_READY = json.dumps({"ready": False, "reason": "login QR code shown"})


def tools(ctx):
    return {t.name: t for t in messaging.build(ctx)}


def write_contacts(ctx, data):
    ctx.config.contacts_file.write_text(json.dumps(data))


@pytest.mark.parametrize("raw,expected", [
    ("+44 7700 900-123", "447700900123"),
    ("0044 7700 900123", "447700900123"),
    ("(555) 123-4567", "5551234567"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_list_contacts(ctx):
    assert "No contacts saved" in tools(ctx)["list_contacts"]()
    write_contacts(ctx, {"Mum": {"phone": "+44 7700 900123"}})
    assert "mum" in tools(ctx)["list_contacts"]()


def test_send_whatsapp_desktop_to_contact(make_ctx):
    ctx = make_ctx("Darwin", vision=[READY])
    write_contacts(ctx, {"Mum": {"phone": "+44 7700 900123"}})
    out = tools(ctx)["send_whatsapp"](recipient="mum", message="On my way! 5 mins & counting")
    assert out == "WhatsApp message sent to mum (+447700900123)."
    (kind, url), = ctx.executor.calls
    assert kind == "open_url" and url.startswith("whatsapp://send?")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q == {"phone": ["447700900123"], "text": ["On my way! 5 mins & counting"]}
    assert "+" not in url.split("text=")[1]  # spaces encoded as %20 (WhatsApp doesn't decode '+')
    assert ctx.computer.actions == [("press", "enter")]
    assert "On my way!" in ctx.llm.vision_calls[0]


def test_send_whatsapp_web_on_linux_and_raw_number(make_ctx):
    ctx = make_ctx("Linux", vision=[READY])
    tools(ctx)["send_whatsapp"](recipient="+1 555 123 4567", message="hi")
    assert ctx.executor.calls[0][1].startswith("https://web.whatsapp.com/send?phone=15551234567&text=hi")


def test_send_whatsapp_does_not_press_send_if_screen_not_ready(make_ctx):
    ctx = make_ctx("Darwin", vision=[NOT_READY])
    out = tools(ctx)["send_whatsapp"](recipient="+15551234567", message="hi")
    assert "did NOT press send" in out and "QR code" in out
    assert ctx.computer.actions == []


def test_send_whatsapp_vision_garbage_is_safe(make_ctx):
    ctx = make_ctx("Darwin", vision=["not json at all"])
    assert "did NOT press send" in tools(ctx)["send_whatsapp"](recipient="+15551234567", message="hi")
    assert ctx.computer.actions == []


def test_send_whatsapp_unknown_contact(ctx):
    out = tools(ctx)["send_whatsapp"](recipient="Bob", message="hi")
    assert "don't have a WhatsApp number" in out and ctx.executor.calls == []


def test_send_whatsapp_dry_run_skips_vision(make_ctx):
    ctx = make_ctx("Darwin", dry_run=True)
    assert "sent" in tools(ctx)["send_whatsapp"](recipient="+15551234567", message="hi")
    assert ctx.llm.vision_calls == []


def test_imessage_uses_argv_not_string_interpolation(make_ctx):
    ctx = make_ctx("Darwin")
    write_contacts(ctx, {"Alex": {"phone": "+15551234567", "imessage": "alex@example.com"}})
    evil = 'hi" & do shell script "rm -rf ~'
    out = tools(ctx)["send_imessage"](recipient="Alex", message=evil)
    assert out == "iMessage sent to Alex (alex@example.com)."
    (_, args, shell), = ctx.executor.calls
    assert not shell
    assert args[:2] == ["osascript", "-e"] and args[3:] == ["alex@example.com", evil]
    assert evil not in args[2]


def test_imessage_requires_macos(make_ctx):
    ctx = make_ctx("Windows")
    assert "only works on macOS" in tools(ctx)["send_imessage"](recipient="x", message="y")
    assert ctx.executor.calls == []


def test_imessage_failure(make_ctx):
    from jarvis.executor import CommandResult

    ctx = make_ctx("Darwin")
    ctx.executor.results["osascript"] = CommandResult(1, stderr="Can't get participant")
    assert "iMessage failed: Can't get participant" in tools(ctx)["send_imessage"](recipient="+1555", message="y")


def test_messaging_tools_are_sensitive(ctx):
    t = tools(ctx)
    assert t["send_whatsapp"].sensitive and t["send_imessage"].sensitive and not t["list_contacts"].sensitive


def test_applescript_compiles_on_macos():
    import shutil
    import subprocess

    if not shutil.which("osacompile"):
        pytest.skip("macOS only")
    subprocess.run(["osacompile", "-o", "/dev/null", "-e", messaging.IMESSAGE_SCRIPT], check=True)
