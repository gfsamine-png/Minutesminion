from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import tempfile
import os
from app.validation import validate_extension, validate_duration, ValidationError
from app.transcription import transcribe

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    validate_extension(file.filename)

    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        duration = validate_duration(tmp_path)
    except ValidationError as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))

   transcript = transcribe(tmp_path)
    os.remove(tmp_path)

    return {
        "transcript": transcript,
        "duration_seconds": duration,
    }