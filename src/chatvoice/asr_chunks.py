"""Bounded sequential file decoding for large ASR uploads."""

from __future__ import annotations

from contextlib import suppress
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable
import wave


class AudioProcessingCancelled(RuntimeError):
    """The owning import has been cancelled before result commit."""


def transcribe_file(
    source: Path,
    provider: Callable[[bytes, int], dict[str, Any]],
    *,
    cancelled: Callable[[], bool] | None = None,
    chunk_seconds: int = 30,
    max_seconds: float = 900,
) -> dict[str, Any]:
    """Decode one 16-kHz mono PCM window at a time without loading a GPU model."""
    started = time.monotonic()

    def check() -> None:
        if cancelled and cancelled():
            raise AudioProcessingCancelled("audio processing cancelled")
        if time.monotonic() - started > max_seconds:
            raise TimeoutError("audio processing time budget exceeded")

    check()
    binary = shutil.which("ffmpeg")
    if not binary:
        raise RuntimeError("large audio requires ffmpeg")
    source = Path(source)
    if not 1 <= chunk_seconds <= 120:
        raise ValueError("invalid audio chunk duration")
    raw_parts: list[str] = []
    corrected_parts: list[str] = []
    count = 0
    frames = 0
    with tempfile.TemporaryFile(dir=str(source.parent)) as errors:
        process = subprocess.Popen(
            [
                binary, "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "file,pipe", "-i", str(source),
                "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        try:
            while True:
                check()
                pcm = process.stdout.read(16000 * 2 * chunk_seconds)
                if not pcm:
                    break
                if len(pcm) % 2:
                    raise ValueError("decoded PCM is incomplete")
                check()
                output = io.BytesIO()
                with wave.open(output, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(pcm)
                count += 1
                frames += len(pcm) // 2
                result = provider(output.getvalue(), count)
                check()
                if not isinstance(result, dict):
                    raise ValueError("ASR returned invalid chunk result")
                for field in ("raw_text", "corrected_text"):
                    if field in result and not isinstance(result[field], str):
                        raise ValueError("ASR returned invalid chunk text")
                raw = result.get("raw_text") or result.get("corrected_text") or ""
                corrected = result.get("corrected_text") or raw
                if raw.strip():
                    raw_parts.append(raw.strip())
                if corrected.strip():
                    corrected_parts.append(corrected.strip())
            if process.wait() != 0:
                raise ValueError("audio decoding failed; choose a valid supported audio container")
            if count == 0:
                raise ValueError("audio contains no decodable samples")
        finally:
            if process.poll() is None:
                # FFmpeg's stdin quit protocol, not a process signal. Drain its pipe.
                with suppress(BrokenPipeError, OSError):
                    process.stdin.write(b"q\n")
                    process.stdin.flush()
                while process.stdout.read(1024 * 1024):
                    pass
                process.wait()
            process.stdout.close()
            with suppress(BrokenPipeError, OSError):
                process.stdin.close()
    return {
        "raw_text": "\n".join(raw_parts),
        "corrected_text": "\n".join(corrected_parts),
        "chunks": count,
        "seconds": frames / 16000,
    }
