import os
from mutagen import File as MutagenFile

from app.config import ALLOWED_AUDIO_EXTENSIONS, MAX_AUDIO_DURATION_SECONDS


class ValidationError(Exception):
    pass


def validate_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValidationError(f"Unsupported file type '{ext}'. Please upload .mp3 or .wav.")
    
def validate_duration(file_path: str) -> float:
    audio = MutagenFile(file_path)
    if audio is None or audio.info is None:
        raise ValidationError("Could not read audio file. It may be corrupted.")

    duration = audio.info.length
    if duration > MAX_AUDIO_DURATION_SECONDS:
        raise ValidationError("Audio too long. Please keep voice notes under 60 seconds.")
    return duration