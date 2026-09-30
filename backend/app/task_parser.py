import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Groq deprecated the llama-3.3-70b-versatile model. openai/gpt-oss-120b is
# the current recommended general-purpose/reasoning model on Groq.
GROQ_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT_TEMPLATE = """You extract actionable tasks from a spoken voice note transcript.

Today's date is {today} ({weekday}).

Here is a lookup table mapping the next 8 days to their exact dates. Use this table
to resolve any date reference — do NOT calculate dates yourself, only look them up here:

{date_table}

For each task, determine whether it has a SPECIFIC, SCHEDULABLE date AND time.

Set "has_datetime" to true ONLY when BOTH a specific day and a specific time are
clearly stated. In that case, set "scheduled_at" to the combined date+time
(YYYY-MM-DDTHH:MM:SS), and leave "needs_time" false and "known_date" null.

If a SPECIFIC DAY is mentioned (using the lookup table above) but NO time is given,
set "has_datetime" to false, set "needs_time" to true, and set "known_date" to that
day's date from the table (YYYY-MM-DD format, no time). This tells the system the
day is known but the time still needs to be asked for.

If neither a specific day nor a specific time is mentioned, or only a time is
mentioned with no day, set "has_datetime" false, "needs_time" false, "known_date"
null, and "scheduled_at" null. Vague references like "soon" or "next week" (with
no specific day) do not count as a specific day.

Resolving a bare weekday name (e.g. "Thursday", "Tuesday") with no other qualifier:
find that weekday name in the table above and use the exact date listed next to it.
The table already correctly handles same-day and next-occurrence cases — just copy
the date from the matching row, do not add or subtract days yourself.

Return ONLY a JSON array of task objects, nothing else. No preamble, no markdown, no code fences.
Each object must follow this exact structure:
{{"text": "the task description", "has_datetime": true or false, "scheduled_at": "YYYY-MM-DDTHH:MM:SS" or null, "needs_time": true or false, "known_date": "YYYY-MM-DD" or null}}

If there are no clear action items, return an empty array: []

Example input: "please remember to update the readme file, meet the client friday at 3pm, and call the vendor thursday"
Example output:
[
  {{"text": "Update the readme file", "has_datetime": false, "scheduled_at": null, "needs_time": false, "known_date": null}},
  {{"text": "Meet the client", "has_datetime": true, "scheduled_at": "2026-07-24T15:00:00", "needs_time": false, "known_date": null}},
  {{"text": "Call the vendor", "has_datetime": false, "scheduled_at": null, "needs_time": true, "known_date": "2026-07-30"}}
]
"""


def _build_date_lookup_table(now: datetime) -> str:
    """Precomputes the next 8 days with their exact dates, so the LLM only
    needs to match a mentioned weekday to a row rather than calculate
    dates itself — arithmetic is a known LLM weak point, lookup is not."""
    lines = []
    for i in range(8):
        d = now + timedelta(days=i)
        label = "today" if i == 0 else ("tomorrow" if i == 1 else "")
        suffix = f" ({label})" if label else ""
        lines.append(f"{d.strftime('%A')}{suffix} = {d.strftime('%Y-%m-%d')}")
    return "\n".join(lines)


def extract_tasks(transcript: str) -> list[dict]:
    if not transcript or not transcript.strip():
        return []

    now = datetime.now()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        today=now.strftime("%Y-%m-%d"),
        weekday=now.strftime("%A"),
        date_table=_build_date_lookup_table(now),
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    try:
        tasks = json.loads(raw)
        if not isinstance(tasks, list):
            return []

        cleaned = []
        for t in tasks:
            if not isinstance(t, dict) or "text" not in t:
                continue
            cleaned.append({
                "text": t.get("text", ""),
                "has_datetime": bool(t.get("has_datetime", False)),
                "scheduled_at": t.get("scheduled_at"),
                "needs_time": bool(t.get("needs_time", False)),
                "known_date": t.get("known_date"),
            })
        return cleaned
    except json.JSONDecodeError:
        return []


def generate_daily_summary(all_tasks: list[str]) -> dict:
    if not all_tasks:
        return {
            "total_tasks": 0,
            "repeated_tasks": [],
            "important_tasks": [],
            "summary_text": "No tasks were recorded yesterday."
        }

    tasks_text = "\n".join(f"- {t}" for t in all_tasks)

    prompt = f"""Here is a list of tasks extracted from voice notes over the past day:

{tasks_text}

Analyze this list and return ONLY a JSON object with this exact structure, nothing else:
{{
  "repeated_tasks": ["tasks that appear more than once, or are clearly duplicates/near-duplicates"],
  "important_tasks": ["tasks that seem urgent, client-facing, or time-sensitive"],
  "summary_text": "a short 2-3 sentence plain-English summary of the day's tasks"
}}
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You summarize daily task lists. Return ONLY valid JSON, no preamble."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
        result["total_tasks"] = len(all_tasks)
        return result
    except json.JSONDecodeError:
        return {
            "total_tasks": len(all_tasks),
            "repeated_tasks": [],
            "important_tasks": [],
            "summary_text": "Summary generation failed."
        }


def answer_question(question: str, context_notes: list[dict]) -> str:
    """Given a question and a list of relevant past notes (each with
    id/transcript/created_at), asks Groq to answer using ONLY that
    context — this is the 'generation' half of RAG, following the
    'retrieval' half done by search_similar_notes()."""
    context_text = "\n".join(
        f"- [{n['created_at'][:10]}] {n['transcript']}" for n in context_notes
    )

    prompt = f"""Here are some past notes that may be relevant to a question:

{context_text}

Question: {question}

Answer the question using ONLY the information in these notes. If the notes don't
contain enough information to answer confidently, say so clearly rather than
guessing. Keep the answer to 2-3 sentences, plain English, no preamble.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You answer questions using only the provided notes as context. Be concise and honest about uncertainty."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    return response.choices[0].message.content.strip()