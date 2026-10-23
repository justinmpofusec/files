import array
import io
import math
import shutil
import subprocess
import wave

import pytest

from jarvis.voice import Endpointer, Listener, Speaker, clean_for_speech, rms, to_wav

RATE = 16000
FRAME = 800  # 50 ms


def frame(amplitude: int) -> bytes:
    return array.array("h", (int(amplitude * math.sin(2 * math.pi * 440 * i / RATE)) for i in range(FRAME))).tobytes()


def script(*parts):
    """parts: (amplitude, n_frames) pairs -> frame generator."""
    def gen():
        for amp, n in parts:
            for _ in range(n):
                yield frame(amp)
        while True:  # a real mic never ends; the endpointer must stop us
            yield frame(0)
    return gen


def test_clean_for_speech():
    text = "**Done!** Opened [Spotify](https://spotify.com).\n- item one\n`code` see https://x.y/z ```py\nx=1```"
    assert clean_for_speech(text) == "Done! Opened Spotify. item one code see a link (code omitted)"


@pytest.mark.parametrize("os_name,first", [("Darwin", "say"), ("Linux", "espeak-ng"), ("Windows", "powershell")])
def test_speaker_reads_text_from_stdin(os_name, first):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw["input"]))
        return subprocess.CompletedProcess(cmd, 0)

    sp = Speaker(os_name, voice="Daniel", rate=200, run=fake_run)
    assert sp.say("-rf **Hello** there")
    cmd, spoken = calls[0]
    assert cmd[0] == first and spoken == "-rf Hello there"
    assert "-rf Hello there" not in " ".join(cmd)  # never on the command line
    if os_name == "Darwin":
        assert cmd == ["say", "-r", "200", "-v", "Daniel", "-f", "-"]
    assert sp.say("   ") and len(calls) == 1  # nothing to say -> no process


def test_speaker_missing_binary():
    def boom(cmd, **kw):
        raise FileNotFoundError(cmd[0])

    assert Speaker("Linux", run=boom).say("hi") is False


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
def test_real_tts_engine_runs():
    assert Speaker("Linux").say("Jarvis online.")


@pytest.mark.skipif(not shutil.which("say"), reason="macOS only")
def test_real_macos_say():
    assert Speaker("Darwin").say("Jarvis test.")


def test_rms_and_wav():
    assert rms([3, -4]) == pytest.approx(math.sqrt(12.5)) and rms([]) == 0
    wav = to_wav(b"\x00\x00" * 160, RATE)
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, RATE, 160)


def test_endpointer_stops_after_speech_then_silence():
    ep = Endpointer()
    feeds = [50] * 6 + [3000] * 20 + [60] * 30
    stopped_at = next(i for i, v in enumerate(feeds) if ep.feed(v))
    assert ep.heard_speech and stopped_at == 6 + 20 + 24 - 1


def test_endpointer_gives_up_without_speech_and_caps_length():
    ep = Endpointer()
    n = 0
    while not ep.feed(40):
        n += 1
    assert not ep.heard_speech and n + 1 == ep.no_speech_frames
    ep = Endpointer()
    n = 1
    while not ep.feed(5000 if n > 6 else 40):
        n += 1
    assert n == ep.max_frames  # nonstop talking is capped


def test_endpointer_noise_floor_handles_loud_room_and_instant_talker():
    ep = Endpointer()
    for v in [2000, 2000, 2000, 2000, 2000, 2000]:  # noisy room
        ep.feed(v)
    assert ep.threshold == 6000
    ep = Endpointer()
    for v in [40, 3000, 3000, 3000, 3000, 3000]:  # started talking immediately
        ep.feed(v)
    assert ep.threshold == 350


def test_listener_records_one_utterance():
    wav = Listener(frames=script((0, 6), (4000, 30), (0, 10))).record()
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == RATE
        assert w.getnframes() == FRAME * (6 + 30 + 24)  # trailing silence trimmed by the endpointer


def test_listener_returns_none_on_silence():
    assert Listener(frames=script((0, 1))).record() is None


def test_microphone_error_is_friendly(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(RuntimeError, match="pip install sounddevice"):
        Listener().record()


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
def test_endpointer_on_real_synthesized_speech(tmp_path):
    """Real speech audio (from espeak-ng) with silence before and after goes through the Listener."""
    path = tmp_path / "speech.wav"
    subprocess.run(["espeak-ng", "-w", str(path), "Jarvis, open Spotify and play some music."], check=True)
    with wave.open(str(path)) as w:
        rate, pcm = w.getframerate(), w.readframes(w.getnframes())
    block = int(rate * 0.05) * 2
    silence = b"\x00\x00" * (rate // 2)
    audio = silence + pcm + b"\x00\x00" * rate * 3

    def frames():
        for i in range(0, len(audio), block):
            yield audio[i:i + block]

    wav = Listener(samplerate=rate, frames=frames).record()
    assert wav is not None
    with wave.open(io.BytesIO(wav)) as w:
        seconds = w.getnframes() / rate
    speech_seconds = len(pcm) / 2 / rate
    assert speech_seconds < seconds < speech_seconds + 0.5 + 1.6  # stopped ~1.2 s after speech ended
