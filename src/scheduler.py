import json

from openai import OpenAI

from .config import OPENAI_API_KEY, TIME_SLOTS

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """\
You are a daily schedule planner. You receive a list of tasks with priorities and must \
assign them to 30-minute time slots throughout the day (6:00 to 23:30).

CRITICAL RULES — follow these exactly:

1. TIME-LOCKED TASKS: If a task name contains a specific time like "12pm", "12 - 12:30", \
"3:30 PM", "9am", etc., you MUST place it at exactly that time. This overrides all other rules. \
Parse times carefully from task names. "12pm" = 12:00. "12 - 12:30" = 12:00 to 12:30.

2. NO DUPLICATES: Each task appears ONCE (or in consecutive slots if it needs more time). \
Never put the same task in non-consecutive slots. Never repeat a task name.

3. DURATION: Unless a task specifies duration (e.g. "should take 10 mins" = 1 slot, \
"2 hour meeting" = 4 slots), assume each task takes exactly ONE 30-minute slot.

4. PRIORITY ORDER for scheduling remaining (non-time-locked) tasks:
   - Imp Urg: schedule in peak focus hours (9:00-12:00)
   - Urg ~Imp: schedule in afternoon (13:00-17:00)
   - Imp ~Urg: fit into available focused time
   - In Progress: give dedicated blocks
   - ~Imp ~Urg: fill evening gaps (17:00-21:00)

5. FILL STRATEGY: You only have the tasks provided. Do NOT invent new tasks. \
Slots without tasks should be "Free time" (not "Break"). Only use "Break" for \
intentional buffer after a demanding task.

6. Pinned tasks are recurring/daily habits — schedule them in evening or light slots.

Return ONLY valid JSON — an array of objects with "time" and "activity" keys.
Use the exact time format from the available slots (e.g. "7:00", "7:30", "13:00").
Every slot from 6:00 to 23:30 must appear exactly once in your output.
"""


def generate_schedule(
    tasks: list[dict],
    current_schedule: list[list[str]] | None = None,
) -> list[dict]:
    """Use OpenAI to generate a daily schedule from a list of tasks."""

    task_lines = []
    for t in tasks:
        line = f"- [{t['status']}] {t['name']}"
        if t.get("weekday") == "Pinned":
            line += " (Pinned/recurring)"
        if t.get("details"):
            line += f"\n  Details:\n{t['details']}"
        task_lines.append(line)

    user_msg = f"Tasks to schedule:\n" + "\n".join(task_lines)
    user_msg += f"\n\nAvailable time slots: {', '.join(TIME_SLOTS)}"

    if current_schedule:
        user_msg += "\n\nCurrent schedule for reference (user's existing routines):\n"
        for row in current_schedule:
            if len(row) >= 4:
                if row[1].strip():
                    user_msg += f"  {row[0]}:00 — {row[1]}\n"
                if row[3].strip():
                    user_msg += f"  {row[2]} — {row[3]}\n"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "[]"
    parsed = json.loads(raw)

    if isinstance(parsed, dict):
        for key in ("schedule", "slots", "data", "items"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break
        else:
            parsed = list(parsed.values())[0] if parsed else []

    if not isinstance(parsed, list):
        raise ValueError(f"Expected a list from OpenAI, got: {type(parsed)}")

    return parsed


def format_schedule_preview(schedule: list[dict]) -> str:
    """Format a schedule as a human-readable string for preview."""
    lines = []
    for slot in schedule:
        time = slot.get("time", "??")
        activity = slot.get("activity", "")
        marker = "  " if not activity or activity.lower() in ("free time", "break", "") else ">>"
        lines.append(f"  {marker} {time:>5}  {activity}")

    return "\n".join(lines)
