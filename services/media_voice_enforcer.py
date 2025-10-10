"""Utilities enforcing voice delivery for administrator audio media."""

from __future__ import annotations

import os
import subprocess
import tempfile
from io import BytesIO
from typing import Optional

from core.config import settings
from core.telemetry import logger


class VoiceConversionError(RuntimeError):
    """Raised when voice conversion fails."""


def normalize_media_type(media_type: Optional[str]) -> Optional[str]:
    """Force plain audio into voice mode for bots."""

    if media_type == "audio":
        return "voice"
    return media_type


def should_convert_to_voice(
    source_media_type: Optional[str], target_media_type: Optional[str]
) -> bool:
    """Tell if we must convert to voice format."""

    if target_media_type != "voice":
        return False
    if not source_media_type:
        return True
    return source_media_type != "voice"


def convert_stream_to_voice(stream: BytesIO) -> BytesIO:
    """Convert arbitrary audio stream to Opus voice using ffmpeg."""

    # Preserve current position and rewind for read
    position = stream.tell() if stream.seekable() else None
    try:
        if stream.seekable():
            stream.seek(0)
        voice_bytes = _run_ffmpeg_conversion(stream)
    finally:
        if position is not None:
            stream.seek(position)

    voice_stream = BytesIO(voice_bytes)
    voice_stream.name = "voice.ogg"
    return voice_stream


def _run_ffmpeg_conversion(stream: BytesIO) -> bytes:
    """Execute ffmpeg to transcode stream bytes into OGG Voice."""

    suffix = _detect_suffix(stream)
    ffmpeg_binary = getattr(settings, "FFMPEG_BINARY", "ffmpeg") or "ffmpeg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source_file:
        source_file.write(stream.read())
        source_path = source_file.name

    output_fd, output_path = tempfile.mkstemp(suffix=".ogg")
    os.close(output_fd)

    command = [
        ffmpeg_binary,
        "-y",
        "-i",
        source_path,
        "-vn",
        "-acodec",
        "libopus",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "24000",
        output_path,
    ]

    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or b"").decode(errors="ignore")
            logger.error(
                "Voice conversion failed",
                extra={
                    "return_code": completed.returncode,
                    "stderr_tail": stderr[-400:],
                    "ffmpeg_binary": ffmpeg_binary,
                },
            )
            raise VoiceConversionError("ffmpeg returned non-zero exit code")

        with open(output_path, "rb") as voice_file:
            return voice_file.read()
    except FileNotFoundError as exc:
        logger.error(
            "ffmpeg binary not found for voice conversion",
            extra={"binary": ffmpeg_binary, "error": str(exc)},
        )
        raise VoiceConversionError("ffmpeg binary not available") from exc
    finally:
        _safe_remove(source_path)
        _safe_remove(output_path)


def _detect_suffix(stream: BytesIO) -> str:
    """Infer file suffix from BytesIO name when available."""

    name = getattr(stream, "name", "") or ""
    if "." in name:
        suffix = name.rsplit(".", 1)[-1]
        if suffix:
            return f".{suffix}"
    return ".bin"


def _safe_remove(path: str) -> None:
    """Remove temporary file ignoring missing path errors."""

    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except Exception as exc:  # pragma: no cover - best effort cleanup
        logger.warning(
            "Failed to remove temporary file",
            extra={"path": path, "error": str(exc)},
        )
