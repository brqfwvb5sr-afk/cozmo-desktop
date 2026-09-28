"""Optional local push-to-talk recognition; audio never leaves this machine."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Protocol

from cozmo_desktop.robot.base import RobotError


class SpeechRecognitionProvider(Protocol):
    async def start(self, model_path: Path) -> None: ...

    async def stop(self) -> str: ...

    async def cancel(self) -> None: ...


class VoskPushToTalk:
    """Bounded 16 kHz mono recording and offline Vosk transcription."""

    MAX_BYTES = 16_000 * 2 * 15

    def __init__(self) -> None:
        self._stream: Any = None
        self._model: Any = None
        self._audio = bytearray()
        self._lock = threading.Lock()

    async def start(self, model_path: Path) -> None:
        if self._stream is not None:
            raise RobotError("Microphone is already listening.")
        if not str(model_path).strip() or not await asyncio.to_thread(model_path.is_dir):
            raise RobotError("Choose a downloaded local Vosk model folder in Settings.")
        stream = None
        try:
            import sounddevice as sd
            from vosk import Model
        except ImportError as exc:
            raise RobotError(
                "Local speech recognition needs the optional voice dependencies."
            ) from exc
        try:
            model = await asyncio.to_thread(Model, str(model_path))
            with self._lock:
                self._audio.clear()

            def receive(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
                del frames, time_info, status
                with self._lock:
                    remaining = self.MAX_BYTES - len(self._audio)
                    self._audio.extend(bytes(indata)[:remaining])

            stream = sd.RawInputStream(
                samplerate=16000, channels=1, dtype="int16", blocksize=4000, callback=receive
            )
            await asyncio.to_thread(stream.start)
        except Exception as exc:
            if stream is not None:
                await asyncio.to_thread(stream.close)
            raise RobotError("Microphone or local speech model could not start.") from exc
        self._model = model
        self._stream = stream

    async def stop(self) -> str:
        if self._stream is None:
            raise RobotError("Microphone is not listening.")
        stream, model = self._stream, self._model
        self._stream = None
        self._model = None
        try:
            await asyncio.to_thread(stream.stop)
            await asyncio.to_thread(stream.close)
        except Exception as exc:
            raise RobotError("Could not stop microphone recording.") from exc
        with self._lock:
            audio = bytes(self._audio)
            self._audio.clear()
        if not audio:
            raise RobotError("No microphone audio was captured.")

        def transcribe() -> str:
            from vosk import KaldiRecognizer

            recognizer = KaldiRecognizer(model, 16000)
            recognizer.AcceptWaveform(audio)
            result = json.loads(recognizer.FinalResult())
            return str(result.get("text", "")).strip()

        try:
            text = await asyncio.to_thread(transcribe)
        except Exception as exc:
            raise RobotError("Local speech recognition failed.") from exc
        if not text:
            raise RobotError("No speech recognized. Try again or type your message.")
        return text[:400]

    async def cancel(self) -> None:
        stream = self._stream
        self._stream = None
        self._model = None
        if stream is not None:
            await asyncio.to_thread(stream.close)
        with self._lock:
            self._audio.clear()
