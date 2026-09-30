from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import tempfile
import os
from app.validation import validate_extension, validate_duration, ValidationError
from app.transcription import transcribe
from app.task_parser import extract_tasks, generate_daily_summary, answer_question
from app.database import (
    save_processed_note,
    get_yesterdays_notes,
    get_all_notes,
    toggle_task,
    init_db,
    search_similar_notes,
    schedule_task,
)
from app.calendar_service import create_calendar_event
from app.embedding_service import embed_text
from datetime import datetime, timedelta
from pydantic import BaseModel


class TextInput(BaseModel):
    text: str


class AskInput(BaseModel):
    question: str


class TimeInput(BaseModel):
    time: str  # "HH:MM", 24-hour format


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
    which already includes text/has_datetime/scheduled_at/needs_time/known_date."""
    return [
        {
            "id": i,
            "text": t["text"],
            "completed": False,
            "has_datetime": t.get("has_datetime", False),
            "scheduled_at": t.get("scheduled_at"),
            "needs_time": t.get("needs_time", False),
            "known_date": t.get("known_date"),
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
    embedding = embed_text(transcript)

    note = save_processed_note(
        transcript=transcript,
        tasks=tasks,
        duration_seconds=duration,
        filename=file.filename,
        embedding=embedding,
    )

    schedule_calendar_events(tasks)

    return {
        "id": note.id,
        "transcript": transcript,
        "tasks": tasks,
        "duration_seconds": duration,
    }


@app.post("/api/process-text")
async def process_text(payload: TextInput):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    tasks = structure_tasks(extract_tasks(payload.text))
    embedding = embed_text(payload.text)

    note = save_processed_note(
        transcript=payload.text,
        tasks=tasks,
        duration_seconds=None,
        filename=None,
        embedding=embedding,
    )

    schedule_calendar_events(tasks)

    return {
        "id": note.id,
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


@app.patch("/api/notes/{note_id}/tasks/{task_id}/schedule")
def schedule_task_time(note_id: int, task_id: int, payload: TimeInput):
    """Completes a task that had a known day but a missing time — combines
    the previously known_date with the newly provided time, saves it, and
    creates the calendar event now that the task is fully schedulable."""
    session_notes = get_all_notes()
    note_lookup = next((n for n in session_notes if n.id == note_id), None)
    if not note_lookup:
        raise HTTPException(status_code=404, detail="Note not found")

    task = next((t for t in note_lookup.tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.get("known_date"):
        raise HTTPException(status_code=400, detail="This task has no known date to combine with a time")

    try:
        datetime.strptime(payload.time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format")

    scheduled_at = f"{task['known_date']}T{payload.time}:00"

    note = schedule_task(note_id, task_id, scheduled_at)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    create_calendar_event(task["text"], scheduled_at)

    return {"id": note.id, "tasks": note.tasks}


@app.post("/api/ask")
def ask(payload: AskInput):
    """RAG endpoint: embeds the question, finds the most semantically
    similar past notes via pgvector, and asks Groq to answer the
    question using only those notes as context."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    question_embedding = embed_text(payload.question)
    similar_notes = search_similar_notes(question_embedding, limit=5)

    if not similar_notes:
        return {
            "answer": "No past notes were found to answer this question from.",
            "sources": [],
        }

    context = [
        {"id": n.id, "transcript": n.transcript, "created_at": n.created_at.isoformat()}
        for n in similar_notes
    ]

    answer = answer_question(payload.question, context)

    return {
        "answer": answer,
        "sources": context,
    }