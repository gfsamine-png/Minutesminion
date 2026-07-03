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