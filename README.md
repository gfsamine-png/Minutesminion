<div align="center">

# MinutesMinion

### Audio Milestone Task Router

Turn a voice note or a quick line of text into structured, trackable, schedulable tasks — automatically.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Roadmap](#roadmap)

---

## Overview

MinutesMinion captures a note — spoken or typed — and turns it into a structured task list, without any manual effort. Audio is transcribed locally with Whisper, an LLM (Groq / Llama 3.3) extracts actionable tasks and detects any specific date or time mentioned, and anything schedulable is automatically created as a real Google Calendar event. A scheduled automation delivers a daily summary of the previous day's activity by email and logs it to a spreadsheet.

The system is designed around a clear architectural boundary: **all reasoning (transcription, extraction, scheduling) lives in the backend**, while **automation (n8n) only handles timing and delivery**. This keeps the core logic independently testable and reusable, regardless of which automation tool sits on top of it.

---

## Features

**Capture**
- Record a voice note directly in the browser, or upload an `.mp3` / `.wav` file
- Type a note directly, skipping transcription entirely
- Both input methods converge on the same processing pipeline and results view

**Understanding**
- Local Whisper transcription (no external API call for audio-to-text)
- LLM-based task extraction, robust to imperfect/garbled transcripts
- Automatic detection of specific, schedulable dates and times within tasks (e.g. "Friday at 3pm"), with correct forward-resolution of relative dates

**Action**
- Detected date/time tasks are automatically created as Google Calendar events, in real time
- Task completion is tracked and persisted per task, not just in the browser
- A History page lists every past note with live, saved completion state

**Automation**
- A scheduled daily workflow (n8n) summarizes the previous day's tasks via LLM, classifying repeated and high-priority items
- The summary is emailed and logged as a new row in a Google Sheet
- Days with zero tasks are automatically skipped, avoiding noise

---

## Architecture

```
                    ┌─────────────────────────┐
                    │   Next.js Frontend       │
                    │   (Capture + History)    │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │      FastAPI Backend     │
                    │                          │
     audio ────────►│  Whisper (transcription) │
                    │            │             │
     text  ────────►│            ▼             │
                    │  Groq / Llama 3.3        │
                    │  (task + date/time       │
                    │   extraction)            │
                    └───────┬─────────┬────────┘
                            │         │
                 ┌──────────▼──┐   ┌──▼───────────────────┐
                 │ PostgreSQL   │   │ Google Calendar       │
                 │ (all notes)  │   │ (service account)     │
                 └──────────────┘   └───────────────────────┘

                    ┌─────────────────────────┐
                    │  n8n (Docker, separate)  │
                    │                          │
                    │  Schedule Trigger (8am)  │
                    │           │              │
                    │           ▼              │
                    │  GET /api/daily-summary  │
                    │           │              │
                    │           ▼              │
                    │  IF total_tasks > 0      │
                    │      ├──► Email          │
                    │      └──► Google Sheets  │
                    └──────────────────────────┘
```

**Why n8n only handles scheduling, not reasoning:** the LLM calls that classify and summarize tasks happen inside the FastAPI backend itself, not in an n8n node. This means the extraction and summarization logic can be tested directly (via the interactive API docs) independent of whether n8n is even running, and could be reused by any other client in the future.

**Why Calendar uses a service account but Sheets uses OAuth:** Calendar access is a backend-to-API call with no human involved, so a non-interactive service account is the correct fit. The Sheets integration runs through n8n's own Google Sheets node, which is built around a human authorizing access — so OAuth is the natural mechanism there instead.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Database | PostgreSQL + SQLAlchemy |
| Transcription | OpenAI Whisper (tiny, local) |
| Task extraction & summarization | Groq API — Llama 3.3 70B Versatile |
| Frontend | Next.js + React (TypeScript) |
| Automation | n8n (Docker) |
| Calendar integration | Google Calendar API (service account) |
| Spreadsheet logging | Google Sheets API (OAuth via n8n) |
| Containerization | Docker + Docker Compose |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI routes
│   ├── config.py                # constants (max duration, allowed extensions)
│   ├── validation.py             # file validation (ffprobe-based duration check)
│   ├── transcription.py          # Whisper wrapper
│   ├── task_parser.py             # Groq prompts: extraction + daily summary
│   ├── calendar_service.py        # Google Calendar service account integration
│   └── database.py                # SQLAlchemy models + queries
├── Dockerfile
├── requirements.txt
└── google-calendar-credentials.json   # service account key (gitignored)

frontend/
├── app/
│   ├── page.tsx                 # Capture page (Voice/Text, recording)
│   └── history/
│       └── page.tsx              # History page (persistent checkboxes)
└── Dockerfile

docker-compose.yml
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- A Groq API key
- A Google Cloud project with the Calendar API enabled and a service account key

### Environment Variables

Create a `.env` file in `backend/`:

```
DATABASE_URL=postgresql://<user>:<password>@db:5432/minutesminion
GROQ_API_KEY=<your Groq API key>
```

Place your Google Calendar service account key at `backend/google-calendar-credentials.json`, and share your target calendar with that service account's email, granting **"Make changes to events."**

### Run with Docker Compose

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend + interactive API docs: `http://localhost:8000/docs`

### Run without Docker (local development)

```bash
# Backend
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Optional: n8n Automation

```bash
docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n \
  -e GENERIC_TIMEZONE="Africa/Tunis" -e TZ="Africa/Tunis" \
  docker.n8n.io/n8nio/n8n
```
Configure a workflow: Schedule Trigger → HTTP Request (`GET http://host.docker.internal:8000/api/daily-summary`) → IF (`total_tasks > 0`) → Send Email + Google Sheets append.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/process-audio` | Upload audio → transcribe → extract tasks → save → schedule calendar events |
| `POST` | `/api/process-text` | Submit text → extract tasks → save → schedule calendar events |
| `GET` | `/api/notes` | List all processed notes, most recent first |
| `PATCH` | `/api/notes/{note_id}/tasks/{task_id}` | Toggle a task's completed state |
| `GET` | `/api/daily-summary` | Returns yesterday's task summary and classification |

---

## Roadmap

- [ ] Persist task completion from the Capture page (currently only the History page saves checkbox state)
- [ ] Automated evaluation harness for task-extraction accuracy
- [ ] Production deployment (Vercel + Render)
- [ ] Natural-language search over note history (RAG)