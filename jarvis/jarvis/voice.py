"""Voice: Jarvis speaks replies (macOS `say`, espeak on Linux, SAPI on Windows) and listens through the
microphone (sounddevice), sending the recording to Gemini for transcription."""

from __future__ import annotations

import io
import math
import re
import subprocess
import wave
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------- speaking


def clean_for_speech(text: str) -> str:
    """Remove markdown and URLs so the voice doesn't read out symbols."""
    text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[`*_#>|~]", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Speaker:
    os_name: str
    voice: str = ""
    rate: int = 190
    run: Callable[..., Any] = subprocess.run  # injectable for tests

    def command(self) -> list[str]:
        """Command that reads the text to speak from stdin (so text can never be parsed as options)."""
        if self.os_name == "Darwin":
            cmd = ["say", "-r", str(self.rate)]
            if self.voice:
                cmd += ["-v", self.voice]
            return cmd + ["-f", "-"]
        if self.os_name == "Windows":
            script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      + (f"$s.SelectVoice('{self.voice}'); " if self.voice else "")
                      + "$s.Speak([Console]::In.ReadToEnd())")
            return ["powershell", "-NoProfile", "-Command", script]
        cmd = ["espeak-ng", "-s", str(self.rate)]
        if self.voice:
            cmd += ["-v", self.voice]
        return cmd + ["--stdin"]

    def say(self, text: str) -> bool:
        spoken = clean_for_speech(text)
        if not spoken:
            return True
        try:
            return self.run(self.command(), input=spoken, text=True, capture_output=True, timeout=300).returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


# ---------------------------------------------------------------- listening


@dataclass
class Endpointer:
    """Decides when someone has started and finished talking, from per-frame loudness (RMS) values.

    The first `calibration_frames` measure background noise; speech is anything clearly louder.
    Recording ends after `silence_frames` quiet frames following speech, after `max_frames`, or
    (with no speech at all) after `no_speech_frames`."""

    calibration_frames: int = 6
    silence_frames: int = 24
    max_frames: int = 400
    no_speech_frames: int = 160
    min_threshold: float = 350.0
    noise_factor: float = 3.0
    _noise: list[float] = field(default_factory=list)
    _frames: int = 0
    _quiet: int = 0
    heard_speech: bool = False

    @property
    def threshold(self) -> float:
        noise = min(self._noise) if self._noise else 0.0  # quietest frame: robust if the user talks straight away
        return max(self.min_threshold, noise * self.noise_factor)

    def feed(self, rms: float) -> bool:
        """Returns True when recording should stop."""
        self._frames += 1
        if self._frames <= self.calibration_frames:
            self._noise.append(rms)
            return False
        if rms >= self.threshold:
            self.heard_speech = True
            self._quiet = 0
        elif self.heard_speech:
            self._quiet += 1
        if self._frames >= self.max_frames:
            return True
        if self.heard_speech:
            return self._quiet >= self.silence_frames
        return self._frames >= self.no_speech_frames


def rms(samples: Iterable[int]) -> float:
    values = list(samples)
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def to_wav(pcm: bytes, samplerate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(pcm)
    return buf.getvalue()


class Listener:
    """Records one utterance from the default microphone and returns it as WAV bytes (or None if silent)."""

    def __init__(self, samplerate: int = 16000, frame_seconds: float = 0.05,
                 frames: Callable[[], Iterable[bytes]] | None = None) -> None:
        self.samplerate = samplerate
        self.frame_seconds = frame_seconds
        self._frames = frames or self._microphone_frames

    def _microphone_frames(self) -> Iterable[bytes]:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise RuntimeError(f"Microphone unavailable ({exc}). Install it with `pip install sounddevice`.") from None
        blocksize = int(self.samplerate * self.frame_seconds)
        with sd.RawInputStream(samplerate=self.samplerate, channels=1, dtype="int16", blocksize=blocksize) as stream:
            while True:
                data, _overflowed = stream.read(blocksize)
                yield bytes(data)

    def record(self, endpointer: Endpointer | None = None) -> bytes | None:
        import array

        ep = endpointer or Endpointer()
        chunks: list[bytes] = []
        for frame in self._frames():
            chunks.append(frame)
            if ep.feed(rms(array.array("h", frame))):
                break
        if not ep.heard_speech:
            return None
        return to_wav(b"".join(chunks), self.samplerate)
