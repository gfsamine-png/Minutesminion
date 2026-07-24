import os
import json
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT_TEMPLATE = """You extract actionable tasks from a spoken voice note transcript.

Today's date is {today} ({weekday}).

For each task, determine whether it has a SPECIFIC, SCHEDULABLE date AND time.
Only set "has_datetime" to true when BOTH a specific day and a specific time are
clearly stated or can be confidently resolved using today's date (e.g. "Friday at 3pm",
"tomorrow at 10am", "next Tuesday at noon"). Vague references like "soon", "next week"
(with no specific day), or a day with no time, or a time with no day, must be marked false.

IMPORTANT — resolving a bare weekday name (e.g. "Thursday", "Monday") with no other
qualifier: always resolve it to the NEXT upcoming occurrence of that weekday, counting
forward from today, even if that weekday has already occurred earlier in the current
week. NEVER resolve a bare weekday name to a date in the past. Only resolve to a past
date if the transcript explicitly says so (e.g. "last Thursday").

Return ONLY a JSON array of task objects, nothing else. No preamble, no markdown, no code fences.
Each object must follow this exact structure:
{{"text": "the task description", "has_datetime": true or false, "scheduled_at": "YYYY-MM-DDTHH:MM:SS" or null}}

If there are no clear action items, return an empty array: []

Example input: "please remember to update the readme file and meet the client friday at 3pm"
Example output:
[
  {{"text": "Update the readme file", "has_datetime": false, "scheduled_at": null}},
  {{"text": "Meet the client", "has_datetime": true, "scheduled_at": "2026-07-24T15:00:00"}}
]
"""


def extract_tasks(transcript: str) -> list[dict]:
    if not transcript or not transcript.strip():
        return []

    now = datetime.now()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        today=now.strftime("%Y-%m-%d"),
        weekday=now.strftime("%A"),
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
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
        model="llama-3.3-70b-versatile",
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