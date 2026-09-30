"""
Evaluation harness for MinutesMinion's task extraction.

Runs the REAL extract_tasks() function against a fixed set of curated test
cases (backend/eval_test_cases.json), then uses Groq as a judge to compare
the actual output against the hand-written expected output for each case
(semantic matching, not exact string comparison — different phrasing of the
same task should still count as a match).

This is a standalone developer tool, not part of the live application.
Run it manually whenever task_parser.py's prompt changes, to check for
regressions before/after.

Usage (from inside the backend container):
    docker compose exec backend python -m app.eval
"""

import os
import json
from app.task_parser import extract_tasks, client

TEST_CASES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "eval_test_cases.json",
)


def _judge(expected: list[str], actual: list[str]) -> dict:
    """Asks Groq to semantically compare expected vs actual task lists.
    Returns which expected tasks were matched, which were missed, and
    which actual tasks don't correspond to anything expected (extras/
    hallucinations)."""
    prompt = f"""You are evaluating an AI task-extraction system.

Expected tasks (what SHOULD have been extracted):
{json.dumps(expected)}

Actual tasks (what the system ACTUALLY extracted):
{json.dumps(actual)}

Compare them semantically — different wording for the same underlying task
counts as a match (e.g. "Call the vendor" and "Phone the vendor" are the
same task). Return ONLY a JSON object with this exact structure, nothing else:
{{
  "matched": ["expected tasks that were correctly captured, using the expected wording"],
  "missed": ["expected tasks that were NOT captured at all"],
  "extra": ["actual tasks that don't correspond to any expected task"]
}}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You judge task-extraction accuracy. Return ONLY valid JSON, no preamble."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"matched": [], "missed": expected, "extra": actual}


def run_eval():
    with open(TEST_CASES_PATH) as f:
        test_cases = json.load(f)

    total_expected = 0
    total_matched = 0
    total_extra = 0
    results = []

    for case in test_cases:
        actual_tasks = extract_tasks(case["transcript"])
        actual_texts = [t["text"] for t in actual_tasks]
        expected_texts = case["expected_tasks"]

        judged = _judge(expected_texts, actual_texts)

        total_expected += len(expected_texts)
        total_matched += len(judged["matched"])
        total_extra += len(judged["extra"])

        status = "PASS" if not judged["missed"] and not judged["extra"] else "PARTIAL" if judged["matched"] else "FAIL"

        results.append({
            "id": case["id"],
            "status": status,
            "expected": expected_texts,
            "actual": actual_texts,
            "matched": judged["matched"],
            "missed": judged["missed"],
            "extra": judged["extra"],
        })

    recall = (total_matched / total_expected * 100) if total_expected > 0 else 100.0

    print("\n" + "=" * 60)
    print("MinutesMinion — Task Extraction Evaluation")
    print("=" * 60)
    for r in results:
        marker = {"PASS": "✓", "PARTIAL": "△", "FAIL": "✗"}[r["status"]]
        print(f"{marker} [{r['status']:7}] {r['id']}")
        if r["missed"]:
            print(f"    missed: {r['missed']}")
        if r["extra"]:
            print(f"    extra:  {r['extra']}")
    print("-" * 60)
    print(f"Test cases: {len(results)}")
    print(f"Total expected tasks: {total_expected}")
    print(f"Correctly matched:    {total_matched}")
    print(f"Missed:               {total_expected - total_matched}")
    print(f"Extra/hallucinated:   {total_extra}")
    print(f"Recall: {recall:.1f}%")
    print("=" * 60 + "\n")

    with open("eval_report.json", "w") as f:
        json.dump({
            "recall_percent": round(recall, 1),
            "total_expected": total_expected,
            "total_matched": total_matched,
            "total_extra": total_extra,
            "results": results,
        }, f, indent=2)
    print("Full report saved to eval_report.json\n")


if __name__ == "__main__":
    run_eval()