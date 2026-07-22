import os
import subprocess
import json

from app.config import ALLOWED_AUDIO_EXTENSIONS, MAX_AUDIO_DURATION_SECONDS


class ValidationError(Exception):
    pass


def validate_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Please upload .mp3, .wav, or record directly (.webm)."
        )


def validate_duration(file_path: str) -> float:
    """Uses ffprobe (bundled with ffmpeg, already required by Whisper) to read
    duration for any audio container/codec, including browser-recorded .webm
    files that mutagen cannot reliably parse."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (subprocess.TimeoutExpired, KeyError, ValueError, json.JSONDecodeError, FileNotFoundError):
        raise ValidationError("Could not read audio file. It may be corrupted.")

    if duration > MAX_AUDIO_DURATION_SECONDS:
        raise ValidationError("Audio too long. Please keep voice notes under 60 seconds.")

    return duration
