"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Space_Grotesk, Inter, IBM_Plex_Mono } from "next/font/google";

const display = Space_Grotesk({ subsets: ["latin"], weight: ["500", "700"], variable: "--font-display" });
const body = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

interface Task {
  id: number;
  text: string;
  completed: boolean;
}

interface Note {
  id: number;
  transcript: string;
  tasks: Task[];
  duration_seconds: number | null;
  original_filename: string | null;
  created_at: string;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function History() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingTask, setPendingTask] = useState<string | null>(null);

  useEffect(() => {
    fetchNotes();
  }, []);

  async function fetchNotes() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/notes");
      if (!res.ok) throw new Error("Failed to load history.");
      const data: Note[] = await res.json();
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history.");
    } finally {
      setLoading(false);
    }
  }

  async function toggleTask(noteId: number, taskId: number) {
    const key = `${noteId}-${taskId}`;
    setPendingTask(key);

    // Optimistic update so the UI feels instant
    setNotes((prev) =>
      prev.map((n) =>
        n.id === noteId
          ? {
              ...n,
              tasks: n.tasks.map((t) =>
                t.id === taskId ? { ...t, completed: !t.completed } : t
              ),
            }
          : n
      )
    );

    try {
      const res = await fetch(
        `http://127.0.0.1:8000/api/notes/${noteId}/tasks/${taskId}`,
        { method: "PATCH" }
      );
      if (!res.ok) throw new Error("Failed to update task.");
    } catch (err) {
      // Revert on failure by refetching the real state
      fetchNotes();
      setError(err instanceof Error ? err.message : "Failed to update task.");
    } finally {
      setPendingTask(null);
    }
  }

  return (
    <div className={`${display.variable} ${body.variable} ${mono.variable} page`}>
      <div className="grain" />
      <main className="shell">
        <header className="masthead">
          <div className="masthead-top">
            <div className="wordmark-row">
              <span className="signal-dot" />
              <h1 className="wordmark">MinutesMinion</h1>
            </div>
            <nav className="nav">
              <Link href="/" className="nav-link">Capture</Link>
              <span className="nav-link is-active">History</span>
            </nav>
          </div>
          <p className="eyebrow">All routed notes, most recent first</p>
        </header>

        {error && (
          <div className="error-banner">
            <span className="error-bar" />
            <div>
              <p className="error-title">Something went wrong</p>
              <p className="error-detail">{error}</p>
            </div>
          </div>
        )}

        {loading ? (
          <p className="status-text">Loading history…</p>
        ) : notes.length === 0 ? (
          <div className="empty-state">
            <p className="empty-title">No notes yet</p>
            <p className="empty-detail">
              Notes you capture will show up here, with their tasks tracked over time.
            </p>
            <Link href="/" className="empty-cta">Capture your first note →</Link>
          </div>
        ) : (
          <ul className="note-list">
            {notes.map((note) => {
              const doneCount = note.tasks.filter((t) => t.completed).length;
              const source = note.original_filename ? "Voice" : "Text";
              return (
                <li key={note.id} className="note-card">
                  <div className="note-header">
                    <div className="note-meta">
                      <span className={`source-tag source-${source.toLowerCase()}`}>{source}</span>
                      <span className="note-date">{formatDate(note.created_at)}</span>
                      {note.duration_seconds != null && (
                        <span className="note-duration">{note.duration_seconds.toFixed(1)}s</span>
                      )}
                    </div>
                    <span className="note-progress">
                      {doneCount}/{note.tasks.length} done
                    </span>
                  </div>

                  <p className="note-transcript">{note.transcript}</p>

                  {note.tasks.length === 0 ? (
                    <p className="empty-tasks">No actionable tasks detected.</p>
                  ) : (
                    <ul className="manifest-list">
                      {note.tasks.map((task) => {
                        const key = `${note.id}-${task.id}`;
                        const isPending = pendingTask === key;
                        return (
                          <li
                            key={task.id}
                            className={`manifest-item ${task.completed ? "is-checked" : ""} ${isPending ? "is-pending" : ""}`}
                            onClick={() => toggleTask(note.id, task.id)}
                          >
                            <span className="manifest-index">{String(task.id + 1).padStart(2, "0")}</span>
                            <span className="manifest-check">
                              {task.completed && (
                                <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                                  <path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              )}
                            </span>
                            <span className="manifest-text">{task.text}</span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </main>

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
          margin-bottom: 2.5rem;
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

        .status-text {
          font-family: var(--font-mono), monospace;
          font-size: 0.8rem;
          color: var(--text-tertiary);
        }

        .empty-state {
          background: var(--surface);
          border: 1px dashed var(--border);
          border-radius: 12px;
          padding: 3rem 1.5rem;
          text-align: center;
        }
        .empty-title {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 0.4rem;
        }
        .empty-detail {
          font-size: 0.85rem;
          color: var(--text-secondary);
          margin: 0 0 1.2rem;
          max-width: 380px;
          margin-left: auto;
          margin-right: auto;
        }
        .empty-cta {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--amber);
          text-decoration: none;
        }
        .empty-cta:hover {
          text-decoration: underline;
        }

        .error-banner {
          display: flex;
          gap: 0.8rem;
          margin-bottom: 1.5rem;
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

        .note-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .note-card {
          background: var(--surface);
          border: 1px solid var(--border-soft);
          border-radius: 12px;
          padding: 1.1rem 1.2rem 1.3rem;
        }

        .note-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 0.7rem;
        }

        .note-meta {
          display: flex;
          align-items: center;
          gap: 0.6rem;
        }

        .source-tag {
          font-family: var(--font-mono), monospace;
          font-size: 0.65rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          padding: 0.18rem 0.45rem;
          border-radius: 4px;
          border: 1px solid var(--border);
        }
        .source-voice {
          color: var(--amber);
          border-color: rgba(232, 163, 61, 0.35);
          background: rgba(232, 163, 61, 0.08);
        }
        .source-text {
          color: var(--text-secondary);
          border-color: var(--border);
        }

        .note-date {
          font-family: var(--font-mono), monospace;
          font-size: 0.72rem;
          color: var(--text-tertiary);
        }
        .note-duration {
          font-family: var(--font-mono), monospace;
          font-size: 0.72rem;
          color: var(--text-tertiary);
        }

        .note-progress {
          font-family: var(--font-mono), monospace;
          font-size: 0.7rem;
          color: var(--text-tertiary);
        }

        .note-transcript {
          font-family: var(--font-mono), monospace;
          font-size: 0.82rem;
          line-height: 1.6;
          color: var(--text-secondary);
          margin: 0 0 0.9rem;
          padding-bottom: 0.9rem;
          border-bottom: 1px solid var(--border-soft);
          white-space: pre-wrap;
        }

        .empty-tasks {
          font-size: 0.82rem;
          color: var(--text-tertiary);
          margin: 0;
        }

        .manifest-list {
          list-style: none;
          margin: 0;
          padding: 0;
        }
        .manifest-item {
          display: flex;
          align-items: flex-start;
          gap: 0.65rem;
          padding: 0.5rem 0.15rem;
          border-bottom: 1px solid var(--border-soft);
          cursor: pointer;
          transition: opacity 0.15s ease;
        }
        .manifest-item:last-child {
          border-bottom: none;
        }
        .manifest-item.is-pending {
          opacity: 0.55;
          pointer-events: none;
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
        .manifest-text {
          font-size: 0.87rem;
          line-height: 1.5;
          color: var(--text-primary);
          transition: color 0.15s ease;
        }
        .manifest-item.is-checked .manifest-text {
          color: var(--text-tertiary);
          text-decoration: line-through;
        }
      `}</style>
    </div>
  );
}
