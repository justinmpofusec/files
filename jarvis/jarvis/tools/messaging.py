"""Stage 1: sending messages over WhatsApp (any OS) and iMessage (macOS only)."""

from __future__ import annotations

import json
import re
import urllib.parse

from jarvis.context import Context
from jarvis.tools.base import Tool, tool

IMESSAGE_SCRIPT = """
on run argv
    set targetHandle to item 1 of argv
    set messageText to item 2 of argv
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetParticipant to participant targetHandle of targetService
        send messageText to targetParticipant
    end tell
end run
"""

WHATSAPP_READY_PROMPT = (
    "Look at this screenshot. Is a WhatsApp chat open (desktop app or web.whatsapp.com) with this exact "
    "draft text in the message input box: {text!r}? Reply as JSON: "
    '{{"ready": true|false, "reason": "<short reason>"}}'
)


def normalize_phone(number: str) -> str:
    """'+44 7700 900-123' -> '447700900123' (international format, digits only, as WhatsApp expects)."""
    digits = re.sub(r"\D", "", number)
    if number.strip().startswith("00"):
        digits = digits[2:]
    return digits


def build(ctx: Context) -> list[Tool]:
    os_name = ctx.config.os_name

    def lookup(recipient: str, key: str) -> str | None:
        info = ctx.config.load_contacts().get(recipient.strip().lower())
        if info:
            return info.get(key) or info.get("phone")
        return None

    @tool("List the saved contacts Jarvis can message by name.", read_only=True)
    def list_contacts() -> str:
        contacts = ctx.config.load_contacts()
        if not contacts:
            return f"No contacts saved. Add them to {ctx.config.contacts_file} (see contacts.example.json)."
        return "\n".join(f"{name}: {json.dumps(info)}" for name, info in contacts.items())

    @tool("Send a WhatsApp message. Opens the chat in WhatsApp (desktop app or WhatsApp Web), checks the "
          "screen, then presses Enter to send.", sensitive=True,
          recipient="Contact name from the contacts list, or a phone number in international format (+countrycode...).",
          message="The message text.")
    def send_whatsapp(recipient: str, message: str) -> str:
        number = lookup(recipient, "phone") or recipient
        phone = normalize_phone(number)
        if len(phone) < 7:
            return (f"I don't have a WhatsApp number for {recipient!r}. Use a number with country code, "
                    f"or add them to {ctx.config.contacts_file}.")
        query = urllib.parse.urlencode({"phone": phone, "text": message}, quote_via=urllib.parse.quote)
        use_web = ctx.config.whatsapp_mode == "web" or (ctx.config.whatsapp_mode == "auto" and os_name == "Linux")
        if use_web:
            url, load_seconds = f"https://web.whatsapp.com/send?{query}", 15.0
        else:
            url, load_seconds = f"whatsapp://send?{query}", 5.0
        opened = ctx.executor.open_url(url)
        if not opened.ok:
            return f"Could not open WhatsApp: {opened.stderr}"
        ctx.sleep(load_seconds)

        if not ctx.config.dry_run:
            verdict = _check_screen(ctx, WHATSAPP_READY_PROMPT.format(text=message))
            if not verdict.get("ready"):
                return ("Opened the WhatsApp chat with the message typed, but did NOT press send because I couldn't "
                        f"confirm the chat is ready ({verdict.get('reason', 'unknown')}). The user can press Enter.")
        ctx.computer.press("enter")
        return f"WhatsApp message sent to {recipient} (+{phone})."

    @tool("Send an iMessage via the macOS Messages app. macOS only.", sensitive=True,
          recipient="Contact name from the contacts list, or the phone number / Apple ID email.",
          message="The message text.")
    def send_imessage(recipient: str, message: str) -> str:
        if os_name != "Darwin":
            return "iMessage only works on macOS. Try send_whatsapp instead."
        handle = lookup(recipient, "imessage") or recipient
        # Pass the text as argv, never by string-pasting it into the script, so quotes can't break/inject.
        result = ctx.executor.run(["osascript", "-e", IMESSAGE_SCRIPT, handle, message], timeout=30)
        if not result.ok:
            return f"iMessage failed: {result.stderr.strip()}. Check that Messages is signed in and {handle!r} is valid."
        return f"iMessage sent to {recipient} ({handle})."

    return [list_contacts, send_whatsapp, send_imessage]


def _check_screen(ctx: Context, prompt: str) -> dict:
    try:
        raw = ctx.llm.vision(ctx.computer.screenshot().png, prompt, json_output=True)
        return json.loads(raw)
    except Exception as exc:  # vision failing must not cause a blind send
        return {"ready": False, "reason": f"screen check failed: {exc}"}
