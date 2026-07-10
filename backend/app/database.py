import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from dotenv import load_dotenv

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
def save_processed_note(transcript: str, tasks: list, duration_seconds: float, filename: str):
    session = SessionLocal()
    try:
        note = ProcessedNote(
            transcript=transcript,
            tasks=tasks,
            duration_seconds=duration_seconds,
            original_filename=filename,
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return note
    finally:
        session.close()