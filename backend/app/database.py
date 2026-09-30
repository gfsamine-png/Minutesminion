import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from dotenv import load_dotenv

from app.embedding_service import EMBEDDING_DIMENSIONS

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ProcessedNote(Base):
    __tablename__ = "processed_notes"

    id = Column(Integer, primary_key=True)
    transcript = Column(String, nullable=False)
    tasks = Column(JSON, nullable=False)
    duration_seconds = Column(Float)
    original_filename = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))


def init_db():
    """Enables the pgvector extension (if not already enabled), then
    creates any tables defined by models above that don't already exist.
    Safe to call every time the app starts."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)


from datetime import datetime, timedelta

def get_yesterdays_notes():
    session = SessionLocal()
    try:
        yesterday_start = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday_start.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start + timedelta(days=1)

        notes = session.query(ProcessedNote).filter(
            ProcessedNote.created_at >= yesterday_start,
            ProcessedNote.created_at < yesterday_end
        ).all()

        return notes
    finally:
        session.close()

def save_processed_note(transcript: str, tasks: list, duration_seconds: float, filename: str, embedding: list[float] = None):
    session = SessionLocal()
    try:
        note = ProcessedNote(
            transcript=transcript,
            tasks=tasks,
            duration_seconds=duration_seconds,
            original_filename=filename,
            embedding=embedding,
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return note
    finally:
        session.close()

from sqlalchemy.orm.attributes import flag_modified

def get_all_notes():
    session = SessionLocal()
    try:
        return session.query(ProcessedNote).order_by(ProcessedNote.created_at.desc()).all()
    finally:
        session.close()

def toggle_task(note_id: int, task_id: int):
    session = SessionLocal()
    try:
        note = session.query(ProcessedNote).filter(ProcessedNote.id == note_id).first()
        if not note:
            return None
        for t in note.tasks:
            if t["id"] == task_id:
                t["completed"] = not t["completed"]
        flag_modified(note, "tasks")  # tells SQLAlchemy the JSON field changed in-place
        session.commit()
        session.refresh(note)
        return note
    finally:
        session.close()

def schedule_task(note_id: int, task_id: int, scheduled_at: str):
    """Completes a task that had a known date but a missing time (needs_time),
    by setting its final scheduled_at and marking it fully schedulable.
    Returns the updated note, or None if not found."""
    session = SessionLocal()
    try:
        note = session.query(ProcessedNote).filter(ProcessedNote.id == note_id).first()
        if not note:
            return None
        for t in note.tasks:
            if t["id"] == task_id:
                t["scheduled_at"] = scheduled_at
                t["has_datetime"] = True
                t["needs_time"] = False
        flag_modified(note, "tasks")
        session.commit()
        session.refresh(note)
        return note
    finally:
        session.close()


def search_similar_notes(query_embedding: list[float], limit: int = 5):
    """Returns the notes whose transcript embeddings are most similar to
    the given query embedding, closest first, using pgvector's cosine
    distance operator. Notes with no embedding (e.g. saved before this
    feature existed) are excluded automatically since comparison against
    NULL returns no match."""
    session = SessionLocal()
    try:
        return (
            session.query(ProcessedNote)
            .filter(ProcessedNote.embedding.isnot(None))
            .order_by(ProcessedNote.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .all()
        )
    finally:
        session.close()