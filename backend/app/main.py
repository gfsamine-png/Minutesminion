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
from app.database import get_all_notes
from app.database import toggle_task
from app.database import init_db
from app.task_parser import generate_daily_summary
from app.calendar_service import create_calendar_event
from datetime import datetime, timedelta
from pydantic import BaseModel


class TextInput(BaseModel):
    text: str


app = FastAPI()


@app.on_event("startup")
def on_startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def structure_tasks(extracted_tasks: list[dict]) -> list[dict]:
    """Adds id/completed to each task dict returned by extract_tasks(),
    which already includes text/has_datetime/scheduled_at."""
    return [
        {
            "id": i,
            "text": t["text"],
            "completed": False,
            "has_datetime": t.get("has_datetime", False),
            "scheduled_at": t.get("scheduled_at"),
        }
        for i, t in enumerate(extracted_tasks)
    ]


def schedule_calendar_events(tasks: list[dict]) -> None:
    """For any task flagged with a specific date/time, create a real
    Google Calendar event. Failures are handled inside create_calendar_event
    itself, so this never raises and never blocks the main response."""
    for t in tasks:
        if t.get("has_datetime") and t.get("scheduled_at"):
            create_calendar_event(t["text"], t["scheduled_at"])


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

    tasks = structure_tasks(extract_tasks(transcript))

    save_processed_note(
        transcript=transcript,
        tasks=tasks,
        duration_seconds=duration,
        filename=file.filename,
    )

    schedule_calendar_events(tasks)

    return {
        "transcript": transcript,
        "tasks": tasks,
        "duration_seconds": duration,
    }


@app.post("/api/process-text")
async def process_text(payload: TextInput):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    tasks = structure_tasks(extract_tasks(payload.text))

    save_processed_note(
        transcript=payload.text,
        tasks=tasks,
        duration_seconds=None,
        filename=None,
    )

    schedule_calendar_events(tasks)

    return {
        "transcript": payload.text,
        "tasks": tasks,
    }


@app.get("/api/daily-summary")
def daily_summary():
    notes = get_yesterdays_notes()

    all_tasks = []
    for note in notes:
        all_tasks.extend(t["text"] for t in note.tasks)

    summary = generate_daily_summary(all_tasks)
    summary["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    return summary


@app.get("/api/notes")
def get_notes():
    """Returns all processed notes (audio + text), most recent first.
    Powers the History page on the frontend."""
    notes = get_all_notes()
    return [
        {
            "id": n.id,
            "transcript": n.transcript,
            "tasks": n.tasks,
            "duration_seconds": n.duration_seconds,
            "original_filename": n.original_filename,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]


@app.patch("/api/notes/{note_id}/tasks/{task_id}")
def patch_task(note_id: int, task_id: int):
    """Toggles a single task's completed state within a note."""
    note = toggle_task(note_id, task_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"id": note.id, "tasks": note.tasks}