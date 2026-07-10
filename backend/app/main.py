from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import tempfile
import os
from app.validation import validate_extension, validate_duration, ValidationError
from app.transcription import transcribe
from app.task_parser import extract_tasks
from app.database import save_processed_note
from app.database import get_yesterdays_notes
from app.task_parser import generate_daily_summary
from datetime import datetime, timedelta
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

    tasks = extract_tasks(transcript)

    save_processed_note(
        transcript=transcript,
        tasks=tasks,
        duration_seconds=duration,
        filename=file.filename,
    )

    return {
        "transcript": transcript,
        "tasks": tasks,
        "duration_seconds": duration,
    }
@app.get("/api/daily-summary")
def daily_summary():
    notes = get_yesterdays_notes()

    all_tasks = []
    for note in notes:
        all_tasks.extend(note.tasks)

    summary = generate_daily_summary(all_tasks)
    summary["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    return summary