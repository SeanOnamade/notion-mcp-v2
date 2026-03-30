import json

from openai import OpenAI

from .config import OPENAI_API_KEY, TIME_SLOTS

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """\
You are a daily schedule planner. You receive a list of tasks with priorities and must \
assign them to 30-minute time slots throughout the day (6:00 to 23:30).

Priority levels (highest to lowest):
1. Imp Urg — Important & Urgent: schedule these first, in prime focus hours
2. Urg ~Imp — Urgent, not important: schedule soon but in lighter slots
3. Imp ~Urg — Important, not urgent: fit into available focused time
4. In Progress — Currently being worked on: give dedicated blocks
5. ~Imp ~Urg — Neither important nor urgent: fill remaining gaps
6. Note — Informational, low priority

Rules:
- If a task name contains a specific time (e.g. "12pm", "3:30 PM"), lock it to that slot.
- If a task says "should take X mins", allocate that many 30-min blocks.
- Pinned tasks are recurring/daily — spread them across the day as appropriate.
- Leave some buffer/break slots (mark as "Break" or "Free time").
- Morning (6:00–8:30) is good for routines/warm-up.
- Peak focus hours (9:00–12:00) are best for Imp Urg and deep work.
- Afternoon (13:00–17:00) is good for meetings, calls, and Urg ~Imp tasks.
- Evening (17:00–21:00) is for lighter tasks, Pinned tasks, and ~Imp ~Urg.
- Late night (21:00–23:30) is wind-down: review, reading, prep for next day.
- Multiple related tasks can share a slot if they're quick.
- It's fine to leave some slots empty or as "Free time".

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
