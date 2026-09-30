"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Space_Grotesk, Inter, IBM_Plex_Mono } from "next/font/google";

const display = Space_Grotesk({ subsets: ["latin"], weight: ["500", "700"], variable: "--font-display" });
const body = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

interface Task {
  id: number;
  text: string;
  completed: boolean;
  has_datetime: boolean;
  scheduled_at: string | null;
  needs_time: boolean;
  known_date: string | null;
}

interface ProcessResult {
  id: number;
  transcript: string;
  tasks: Task[];
  duration_seconds?: number;
}

type Mode = "audio" | "text";

function MicIcon({ large }: { large?: boolean }) {
  const size = large ? 28 : 15;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" strokeLinecap="round" />
      <path d="M12 18v4M9 22h6" strokeLinecap="round" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function TextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 6h16M4 12h16M4 18h10" strokeLinecap="round" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 10h18" strokeLinecap="round" />
    </svg>
  );
}

function formatScheduled(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatKnownDate(dateStr: string) {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("audio");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justCompleted, setJustCompleted] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [showUpload, setShowUpload] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [timeInputs, setTimeInputs] = useState<Record<number, string>>({});
  const [schedulingTaskId, setSchedulingTaskId] = useState<number | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [clarifyQueue, setClarifyQueue] = useState<number[]>([]);
  const [modalTime, setModalTime] = useState("");

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setResult(null);
      setError(null);
    }
  }

  function toggleTaskLocal(index: number) {
    if (!result) return;
    const updated = result.tasks.map((t, i) =>
      i === index ? { ...t, completed: !t.completed } : t
    );
    setResult({ ...result, tasks: updated });
  }

  function switchMode(newMode: Mode) {
    if (newMode === mode) return;
    setMode(newMode);
    setResult(null);
    setError(null);
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const recordedFile = new File([blob], "recording.webm", { type: "audio/webm" });
        setFile(recordedFile);
        setResult(null);
        setError(null);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch (err) {
      setError("Microphone access denied or unavailable.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  function formatTime(totalSeconds: number) {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  async function handleSubmit() {
    if (mode === "audio" && !file) return;
    if (mode === "text" && !text.trim()) return;

    setLoading(true);
    setError(null);

    try {
      let res: Response;

      if (mode === "audio") {
        const formData = new FormData();
        formData.append("file", file as File);
        res = await fetch("http://127.0.0.1:8000/api/process-audio", {
          method: "POST",
          body: formData,
        });
      } else {
        res = await fetch("http://127.0.0.1:8000/api/process-text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
      }

      if (!res.ok) {
        const errBody = await res.json();
        throw new Error(errBody.detail || "Something went wrong.");
      }

      const data: ProcessResult = await res.json();
      setResult(data);
      setTimeInputs({});
      setJustCompleted(true);
      setTimeout(() => setJustCompleted(false), 1800);

      const needsClarification = data.tasks
        .filter((t) => t.needs_time && t.known_date)
        .map((t) => t.id);
      setClarifyQueue(needsClarification);
      setModalTime("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetTime(taskId: number, time: string, advanceQueue: boolean) {
    if (!result || !time) return;

    setSchedulingTaskId(taskId);
    setScheduleError(null);

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/notes/${result.id}/tasks/${taskId}/schedule`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ time }),
        }
      );
      if (!res.ok) {
        const errBody = await res.json();
        throw new Error(errBody.detail || "Failed to set time.");
      }
      const data: { id: number; tasks: Task[] } = await res.json();
      setResult({ ...result, tasks: data.tasks });
      if (advanceQueue) {
        setClarifyQueue((prev) => prev.filter((id) => id !== taskId));
        setModalTime("");
      }
    } catch (err) {
      setScheduleError(err instanceof Error ? err.message : "Failed to set time.");
    } finally {
      setSchedulingTaskId(null);
    }
  }

  function skipClarification(taskId: number) {
    setClarifyQueue((prev) => prev.filter((id) => id !== taskId));
    setModalTime("");
  }

  function reopenClarification(taskId: number) {
    setClarifyQueue((prev) => (prev.includes(taskId) ? prev : [taskId, ...prev]));
    setModalTime("");
  }

  const canSubmit = mode === "audio" ? !!file : text.trim().length > 0;
  const checkedCount = result ? result.tasks.filter((t) => t.completed).length : 0;

  return (
    <div className={`${display.variable} ${body.variable} ${mono.variable} page`}>
      <div className="grain" />
      <main className="shell">
        <header className="masthead">
          <div className="masthead-top">
            <div className="wordmark-row">
              <span className={`signal-dot ${loading ? "is-active" : ""} ${justCompleted ? "is-done" : ""}`} />
              <h1 className="wordmark">MinutesMinion</h1>
            </div>
            <nav className="nav">
              <span className="nav-link is-active">Capture</span>
              <Link href="/history" className="nav-link">History</Link>
            </nav>
          </div>
          <p className="eyebrow">Audio Milestone Task Router</p>
        </header>

        <div className="toggle-row" role="tablist" aria-label="Input source">
          <button
            role="tab"
            aria-selected={mode === "audio"}
            className={`toggle-btn ${mode === "audio" ? "is-active" : ""}`}
            onClick={() => switchMode("audio")}
          >
            <MicIcon />
            Voice
          </button>
          <button
            role="tab"
            aria-selected={mode === "text"}
            className={`toggle-btn ${mode === "text" ? "is-active" : ""}`}
            onClick={() => switchMode("text")}
          >
            <TextIcon />
            Text
          </button>
        </div>

        <section className="capture-card">
          {mode === "audio" ? (
            <div className="record-stage">
              <button
                className={`record-fab ${isRecording ? "is-recording" : ""}`}
                onClick={isRecording ? stopRecording : startRecording}
                type="button"
                aria-label={isRecording ? "Stop recording" : "Start recording"}
              >
                {isRecording ? <StopIcon /> : <MicIcon large />}
              </button>

              <p className="record-status">
                {isRecording ? (
                  <span className="record-timer">{formatTime(recordingSeconds)}</span>
                ) : file ? (
                  <span className="record-filename">{file.name}</span>
                ) : (
                  "Tap to record a voice note"
                )}
              </p>

              <button
                className="upload-toggle"
                onClick={() => setShowUpload((v) => !v)}
                type="button"
              >
                {showUpload ? "Hide file upload" : "or upload a file instead"}
              </button>

              {showUpload && (
                <label className="dropzone">
                  <input type="file" accept=".mp3,.wav,.webm" onChange={handleFileChange} hidden />
                  <div className="dropzone-inner">
                    <span className="dropzone-label">
                      {file ? file.name : "Click to select a voice note"}
                    </span>
                    <span className="dropzone-hint">MP3 or WAV</span>
                  </div>
                </label>
              )}
            </div>
          ) : (
            <textarea
              className="text-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe what needs to get done…"
              rows={5}
            />
          )}

          <div className="capture-footer">
            <span className="capture-status">
              {loading ? (
                <span className="status-live">
                  <span className="bars">
                    <i /><i /><i />
                  </span>
                  Processing
                </span>
              ) : (
                <span className="status-idle">Ready to route</span>
              )}
            </span>
            <button className="submit-btn" onClick={handleSubmit} disabled={!canSubmit || loading}>
              {loading ? "Routing…" : "Route to tasks"}
              <span className="arrow">→</span>
            </button>
          </div>
        </section>

        {error && (
          <div className="error-banner">
            <span className="error-bar" />
            <div>
              <p className="error-title">Couldn't process that note</p>
              <p className="error-detail">{error}</p>
            </div>
          </div>
        )}

        {result && (
          <section className="results">
            <div className="panel transcript-panel">
              <div className="panel-header">
                <span className="panel-label">Transcript</span>
                {result.duration_seconds !== undefined && result.duration_seconds !== null && (
                  <span className="panel-meta">{result.duration_seconds.toFixed(1)}s</span>
                )}
              </div>
              <p className="transcript-text">{result.transcript}</p>
            </div>

            <div className="panel manifest-panel">
              <div className="panel-header">
                <span className="panel-label">Tasks</span>
                <span className="panel-meta">
                  {checkedCount}/{result.tasks.length} done
                </span>
              </div>

              {scheduleError && <p className="schedule-error">{scheduleError}</p>}

              {result.tasks.length === 0 ? (
                <p className="empty-tasks">No actionable tasks detected in this note.</p>
              ) : (
                <ul className="manifest-list">
                  {result.tasks.map((task, i) => (
                    <li key={task.id} className="manifest-item-wrap">
                      <div
                        className={`manifest-item ${task.completed ? "is-checked" : ""}`}
                        onClick={() => toggleTaskLocal(i)}
                      >
                        <span className="manifest-index">{String(i + 1).padStart(2, "0")}</span>
                        <span className="manifest-check">
                          {task.completed && (
                            <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                              <path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          )}
                        </span>
                        <span className="manifest-body">
                          <span className="manifest-text">{task.text}</span>
                          {task.has_datetime && task.scheduled_at && (
                            <span className="scheduled-badge">
                              <CalendarIcon />
                              {formatScheduled(task.scheduled_at)}
                            </span>
                          )}
                        </span>
                      </div>

                      {task.needs_time && task.known_date && (
                        <button
                          className="reopen-clarify-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            reopenClarification(task.id);
                          }}
                        >
                          Set time for {formatKnownDate(task.known_date)}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <p className="manifest-note">
                This note isn't saved to History with checks yet — visit History to track completion over time.
              </p>
            </div>
          </section>
        )}
      </main>

      {result && clarifyQueue.length > 0 && (() => {
        const currentTaskId = clarifyQueue[0];
        const currentTask = result.tasks.find((t) => t.id === currentTaskId);
        if (!currentTask || !currentTask.known_date) return null;
        return (
          <div className="clarify-overlay">
            <div className="clarify-modal">
              <span className="clarify-modal-eyebrow">
                Missing time · {clarifyQueue.length} task{clarifyQueue.length === 1 ? "" : "s"} to schedule
              </span>
              <h2 className="clarify-modal-task">{currentTask.text}</h2>
              <p className="clarify-modal-question">
                You said <strong>{formatKnownDate(currentTask.known_date)}</strong> — what time works?
              </p>

              <input
                type="time"
                className="clarify-modal-input"
                value={modalTime}
                onChange={(e) => setModalTime(e.target.value)}
                autoFocus
              />

              {scheduleError && <p className="clarify-modal-error">{scheduleError}</p>}

              <div className="clarify-modal-actions">
                <button
                  className="clarify-modal-skip"
                  onClick={() => skipClarification(currentTaskId)}
                >
                  Skip for now
                </button>
                <button
                  className="clarify-modal-confirm"
                  disabled={!modalTime || schedulingTaskId === currentTaskId}
                  onClick={() => handleSetTime(currentTaskId, modalTime, true)}
                >
                  {schedulingTaskId === currentTaskId ? "Scheduling…" : "Confirm time"}
                  <span className="arrow">→</span>
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      <style jsx global>{`
        * { box-sizing: border-box; }
        html, body {
          margin: 0;
          background: #0f1115;
          color: #edeef2;
        }
      `}</style>

      <style jsx>{`
        .page {
          --bg: #0f1115;
          --surface: #14161c;
          --surface-raised: #1b1e26;
          --border: #2a2f3a;
          --border-soft: #22262f;
          --text-primary: #edeef2;
          --text-secondary: #8b93a3;
          --text-tertiary: #565d6b;
          --amber: #e8a33d;
          --teal: #4fd8c4;
          --danger: #e05a5a;

          font-family: var(--font-body), sans-serif;
          min-height: 100vh;
          position: relative;
          background:
            radial-gradient(ellipse 900px 500px at 20% -10%, rgba(232, 163, 61, 0.06), transparent),
            var(--bg);
        }

        .grain {
          position: fixed;
          inset: 0;
          pointer-events: none;
          background-image: radial-gradient(rgba(255,255,255,0.025) 1px, transparent 1px);
          background-size: 3px 3px;
          opacity: 0.4;
        }

        .shell {
          position: relative;
          max-width: 860px;
          margin: 0 auto;
          padding: 4rem 1.5rem 6rem;
        }

        .masthead {
          margin-bottom: 2.75rem;
        }

        .masthead-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .wordmark-row {
          display: flex;
          align-items: center;
          gap: 0.65rem;
        }

        .signal-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--text-tertiary);
          flex-shrink: 0;
          transition: background 0.3s ease;
        }
        .signal-dot.is-active {
          background: var(--amber);
          animation: pulse 1.1s ease-in-out infinite;
        }
        .signal-dot.is-done {
          background: var(--teal);
          animation: none;
          box-shadow: 0 0 0 4px rgba(79, 216, 196, 0.15);
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(232, 163, 61, 0.35); }
          50% { opacity: 0.6; box-shadow: 0 0 0 5px rgba(232, 163, 61, 0); }
        }

        .wordmark {
          font-family: var(--font-display), sans-serif;
          font-weight: 700;
          font-size: 1.55rem;
          letter-spacing: -0.02em;
          margin: 0;
          color: var(--text-primary);
        }

        .nav {
          display: flex;
          gap: 1.4rem;
        }
        .nav-link {
          font-size: 0.85rem;
          font-weight: 500;
          color: var(--text-tertiary);
          text-decoration: none;
          cursor: pointer;
          transition: color 0.15s ease;
          padding-bottom: 0.2rem;
          border-bottom: 1px solid transparent;
        }
        .nav-link:hover {
          color: var(--text-primary);
        }
        .nav-link.is-active {
          color: var(--amber);
          border-bottom-color: var(--amber);
        }

        .eyebrow {
          font-family: var(--font-mono), monospace;
          font-size: 0.7rem;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--text-tertiary);
          margin: 0.4rem 0 0 1.15rem;
        }

        .toggle-row {
          display: inline-flex;
          padding: 3px;
          background: var(--surface);
          border: 1px solid var(--border-soft);
          border-radius: 8px;
          margin-bottom: 1.25rem;
        }

        .toggle-btn {
          display: flex;
          align-items: center;
          gap: 0.45rem;
          font-family: var(--font-body), sans-serif;
          font-size: 0.83rem;
          font-weight: 500;
          color: var(--text-secondary);
          background: transparent;
          border: none;
          border-radius: 6px;
          padding: 0.5rem 0.9rem;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .toggle-btn:hover:not(.is-active) {
          color: var(--text-primary);
        }
        .toggle-btn.is-active {
          background: var(--surface-raised);
          color: var(--amber);
          border: 1px solid var(--border);
        }

        .capture-card {
          background: var(--surface);
          border: 1px solid var(--border-soft);
          border-radius: 12px;
          padding: 1.1rem;
        }

        .record-stage {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.9rem;
          padding: 1.75rem 1rem 1.4rem;
        }

        .record-fab {
          width: 76px;
          height: 76px;
          border-radius: 50%;
          background: var(--surface-raised);
          border: 1.5px solid var(--amber);
          color: var(--amber);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
          box-shadow: 0 0 0 0 rgba(232, 163, 61, 0.25);
        }
        .record-fab:hover {
          transform: scale(1.04);
          box-shadow: 0 0 0 8px rgba(232, 163, 61, 0.1);
        }
        .record-fab:active {
          transform: scale(0.97);
        }
        .record-fab.is-recording {
          background: rgba(224, 90, 90, 0.12);
          border-color: var(--danger);
          color: #f0b3b3;
          animation: fab-pulse 1.6s ease-in-out infinite;
        }
        @keyframes fab-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(224, 90, 90, 0.28); }
          50% { box-shadow: 0 0 0 12px rgba(224, 90, 90, 0); }
        }

        .record-status {
          margin: 0;
          font-family: var(--font-mono), monospace;
          font-size: 0.85rem;
          color: var(--text-secondary);
          min-height: 1.2em;
        }
        .record-timer {
          color: var(--danger);
          font-weight: 500;
          letter-spacing: 0.02em;
        }
        .record-filename {
          color: var(--teal);
        }

        .upload-toggle {
          background: none;
          border: none;
          font-family: var(--font-body), sans-serif;
          font-size: 0.76rem;
          color: var(--text-tertiary);
          cursor: pointer;
          text-decoration: underline;
          text-underline-offset: 2px;
          padding: 0;
        }
        .upload-toggle:hover {
          color: var(--text-secondary);
        }

        .dropzone {
          display: block;
          cursor: pointer;
          width: 100%;
          margin-top: 0.4rem;
        }
        .dropzone-inner {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          padding: 2.75rem 1rem;
          border: 1px dashed var(--border);
          border-radius: 9px;
          color: var(--text-tertiary);
          transition: border-color 0.15s ease, color 0.15s ease;
        }
        .dropzone:hover .dropzone-inner {
          border-color: var(--amber);
          color: var(--amber);
        }
        .dropzone-label {
          font-size: 0.92rem;
          color: var(--text-secondary);
          font-weight: 500;
        }
        .dropzone:hover .dropzone-label {
          color: var(--text-primary);
        }
        .dropzone-hint {
          font-family: var(--font-mono), monospace;
          font-size: 0.68rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--text-tertiary);
        }

        .text-input {
          width: 100%;
          resize: vertical;
          background: transparent;
          border: 1px dashed var(--border);
          border-radius: 9px;
          padding: 1rem;
          color: var(--text-primary);
          font-family: var(--font-body), sans-serif;
          font-size: 0.92rem;
          line-height: 1.55;
          outline: none;
          transition: border-color 0.15s ease;
        }
        .text-input:focus {
          border-color: var(--amber);
        }
        .text-input::placeholder {
          color: var(--text-tertiary);
        }

        .capture-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 0.9rem;
          padding-top: 0.9rem;
          border-top: 1px solid var(--border-soft);
        }

        .capture-status {
          font-family: var(--font-mono), monospace;
          font-size: 0.72rem;
          letter-spacing: 0.05em;
          color: var(--text-tertiary);
        }
        .status-idle::before {
          content: "○ ";
        }
        .status-live {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          color: var(--amber);
        }
        .bars {
          display: inline-flex;
          align-items: flex-end;
          gap: 2px;
          height: 10px;
        }
        .bars i {
          width: 2px;
          background: var(--amber);
          border-radius: 1px;
          animation: bar 0.9s ease-in-out infinite;
        }
        .bars i:nth-child(1) { height: 40%; animation-delay: 0s; }
        .bars i:nth-child(2) { height: 100%; animation-delay: 0.15s; }
        .bars i:nth-child(3) { height: 65%; animation-delay: 0.3s; }
        @keyframes bar {
          0%, 100% { transform: scaleY(0.4); }
          50% { transform: scaleY(1); }
        }

        .submit-btn {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          font-family: var(--font-body), sans-serif;
          font-size: 0.86rem;
          font-weight: 600;
          background: var(--amber);
          color: #16130a;
          border: none;
          border-radius: 7px;
          padding: 0.55rem 1.05rem;
          cursor: pointer;
          transition: transform 0.1s ease, opacity 0.15s ease;
        }
        .submit-btn:hover:not(:disabled) {
          transform: translateY(-1px);
        }
        .submit-btn:disabled {
          background: var(--surface-raised);
          color: var(--text-tertiary);
          cursor: not-allowed;
        }
        .submit-btn .arrow {
          transition: transform 0.15s ease;
        }
        .submit-btn:hover:not(:disabled) .arrow {
          transform: translateX(2px);
        }

        .error-banner {
          display: flex;
          gap: 0.8rem;
          margin-top: 1rem;
          background: rgba(224, 90, 90, 0.07);
          border: 1px solid rgba(224, 90, 90, 0.25);
          border-radius: 9px;
          padding: 0.85rem 1rem;
        }
        .error-bar {
          width: 3px;
          border-radius: 2px;
          background: var(--danger);
          flex-shrink: 0;
        }
        .error-title {
          margin: 0 0 0.15rem;
          font-size: 0.85rem;
          font-weight: 600;
          color: #f0b3b3;
        }
        .error-detail {
          margin: 0;
          font-size: 0.8rem;
          color: var(--text-secondary);
        }

        .results {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.1rem;
          margin-top: 2rem;
        }
        @media (max-width: 680px) {
          .results { grid-template-columns: 1fr; }
        }

        .panel {
          background: var(--surface);
          border: 1px solid var(--border-soft);
          border-radius: 12px;
          padding: 1.1rem 1.2rem 1.3rem;
        }

        .panel-header {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          margin-bottom: 0.9rem;
          padding-bottom: 0.7rem;
          border-bottom: 1px solid var(--border-soft);
        }
        .panel-label {
          font-family: var(--font-mono), monospace;
          font-size: 0.7rem;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--text-tertiary);
        }
        .panel-meta {
          font-family: var(--font-mono), monospace;
          font-size: 0.7rem;
          color: var(--text-tertiary);
        }

        .transcript-text {
          font-family: var(--font-mono), monospace;
          font-size: 0.85rem;
          line-height: 1.7;
          color: var(--text-secondary);
          margin: 0;
          white-space: pre-wrap;
        }

        .empty-tasks {
          font-size: 0.85rem;
          color: var(--text-tertiary);
          margin: 0;
        }

        .schedule-error {
          font-size: 0.78rem;
          color: #f0b3b3;
          margin: 0 0 0.6rem;
        }

        .manifest-list {
          list-style: none;
          margin: 0;
          padding: 0;
        }
        .manifest-item-wrap {
          border-bottom: 1px solid var(--border-soft);
        }
        .manifest-item-wrap:last-child {
          border-bottom: none;
        }
        .manifest-item {
          display: flex;
          align-items: flex-start;
          gap: 0.65rem;
          padding: 0.55rem 0.15rem;
          cursor: pointer;
        }
        .manifest-index {
          font-family: var(--font-mono), monospace;
          font-size: 0.7rem;
          color: var(--text-tertiary);
          padding-top: 0.15rem;
          flex-shrink: 0;
        }
        .manifest-check {
          width: 15px;
          height: 15px;
          border-radius: 4px;
          border: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--teal);
          flex-shrink: 0;
          margin-top: 0.1rem;
          transition: border-color 0.15s ease, background 0.15s ease;
        }
        .manifest-item.is-checked .manifest-check {
          background: rgba(79, 216, 196, 0.12);
          border-color: var(--teal);
        }
        .manifest-body {
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
        }
        .manifest-text {
          font-size: 0.88rem;
          line-height: 1.5;
          color: var(--text-primary);
          transition: color 0.15s ease;
        }
        .manifest-item.is-checked .manifest-text {
          color: var(--text-tertiary);
          text-decoration: line-through;
        }
        .scheduled-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          width: fit-content;
          font-family: var(--font-mono), monospace;
          font-size: 0.68rem;
          letter-spacing: 0.02em;
          color: var(--amber);
          background: rgba(232, 163, 61, 0.08);
          border: 1px solid rgba(232, 163, 61, 0.25);
          border-radius: 5px;
          padding: 0.15rem 0.45rem;
        }
        .manifest-note {
          margin: 0.9rem 0 0;
          font-size: 0.72rem;
          color: var(--text-tertiary);
          font-style: italic;
        }

        .reopen-clarify-btn {
          width: fit-content;
          background: rgba(232, 163, 61, 0.08);
          border: 1px dashed rgba(232, 163, 61, 0.35);
          border-radius: 6px;
          padding: 0.25rem 0.55rem;
          font-family: var(--font-mono), monospace;
          font-size: 0.68rem;
          color: var(--amber);
          cursor: pointer;
          transition: background 0.15s ease;
        }
        .reopen-clarify-btn:hover {
          background: rgba(232, 163, 61, 0.15);
        }

        .clarify-overlay {
          position: fixed;
          inset: 0;
          background: rgba(6, 7, 9, 0.82);
          backdrop-filter: blur(3px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 50;
          padding: 1.5rem;
          animation: overlay-in 0.18s ease;
        }
        @keyframes overlay-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .clarify-modal {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 2.2rem 2rem;
          max-width: 440px;
          width: 100%;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
          animation: modal-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes modal-in {
          from { opacity: 0; transform: translateY(10px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .clarify-modal-eyebrow {
          display: block;
          font-family: var(--font-mono), monospace;
          font-size: 0.68rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--amber);
          margin-bottom: 0.9rem;
        }
        .clarify-modal-task {
          font-family: var(--font-display), sans-serif;
          font-size: 1.4rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 0.6rem;
          line-height: 1.3;
        }
        .clarify-modal-question {
          font-size: 0.92rem;
          color: var(--text-secondary);
          margin: 0 0 1.5rem;
        }
        .clarify-modal-question strong {
          color: var(--text-primary);
        }

        .clarify-modal-input {
          width: 100%;
          background: var(--surface-raised);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 0.9rem 1rem;
          color: var(--text-primary);
          font-family: var(--font-mono), monospace;
          font-size: 1.4rem;
          text-align: center;
          outline: none;
          transition: border-color 0.15s ease;
        }
        .clarify-modal-input:focus {
          border-color: var(--amber);
        }

        .clarify-modal-error {
          margin: 0.8rem 0 0;
          font-size: 0.8rem;
          color: #f0b3b3;
          text-align: center;
        }

        .clarify-modal-actions {
          display: flex;
          gap: 0.7rem;
          margin-top: 1.6rem;
        }
        .clarify-modal-skip {
          flex-shrink: 0;
          background: transparent;
          border: 1px solid var(--border);
          border-radius: 9px;
          padding: 0 1rem;
          height: 46px;
          color: var(--text-tertiary);
          font-family: var(--font-body), sans-serif;
          font-size: 0.85rem;
          cursor: pointer;
          transition: border-color 0.15s ease, color 0.15s ease;
        }
        .clarify-modal-skip:hover {
          border-color: var(--text-secondary);
          color: var(--text-secondary);
        }
        .clarify-modal-confirm {
          flex: 1;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          background: var(--amber);
          color: #16130a;
          border: none;
          border-radius: 9px;
          height: 46px;
          font-family: var(--font-body), sans-serif;
          font-size: 0.88rem;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.1s ease;
        }
        .clarify-modal-confirm:hover:not(:disabled) {
          transform: translateY(-1px);
        }
        .clarify-modal-confirm:disabled {
          background: var(--border);
          color: var(--text-tertiary);
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}
