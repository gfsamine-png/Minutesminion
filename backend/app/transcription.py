import whisper

_model = None


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("tiny")
    return _model


def transcribe(file_path: str) -> str:
    model = get_model()
    result = model.transcribe(file_path)
    return result["text"].strip()