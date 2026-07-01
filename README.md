# MinutesMinion

Audio Milestone Task Router — upload a short voice note and get an instant, 
interactive task checklist extracted from what you said.

## Tech Stack
- Backend: FastAPI (Python)
- Frontend: Next.js + React (TypeScript)
- Transcription: OpenAI Whisper

## Setup

### Backend
\`\`\`bash
cd backend
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
\`\`\`

### Frontend
\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Backend runs on http://localhost:8000, frontend on http://localhost:3000.