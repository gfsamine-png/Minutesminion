import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """You extract actionable tasks from a spoken voice note transcript.
Return ONLY a JSON array of task strings, nothing else. No preamble, no markdown.
If there are no clear action items, return an empty array: []

Example input: "please remember to update the readme file and email the client the spec"
Example output: ["Update the readme file", "Email the client the spec"]
"""


def extract_tasks(transcript: str) -> list[str]:
    if not transcript or not transcript.strip():
        return []

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    import json
    try:
        tasks = json.loads(raw)
        return tasks if isinstance(tasks, list) else []
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

    import json
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