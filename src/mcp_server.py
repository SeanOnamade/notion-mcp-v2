import json
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from .config import WEEKDAY_MAP
from .notion_ops import get_tasks_for_day, get_current_schedule, write_schedule
from .scheduler import generate_schedule, format_schedule_preview

mcp = FastMCP(
    "notion-schedule-agent",
    description="AI-powered daily schedule planner that reads your Notion tasks and generates optimized half-hour schedules.",
)

_pending_schedule: list[dict] = []


def _resolve_weekday(target: str) -> str:
    """Resolve a target like 'tomorrow', 'monday', etc. to a weekday name."""
    target = target.strip().lower()
    if target == "today":
        return WEEKDAY_MAP[datetime.now().weekday()]
    if target == "tomorrow":
        tomorrow = datetime.now() + timedelta(days=1)
        return WEEKDAY_MAP[tomorrow.weekday()]
    for name in WEEKDAY_MAP.values():
        if target == name.lower():
            return name
    raise ValueError(
        f"Unknown target day: '{target}'. "
        f"Use 'today', 'tomorrow', or a weekday name like 'Monday'."
    )


@mcp.tool()
def get_tasks(day: str) -> str:
    """
    List all tasks from the Upcoming Tasks database for a specific day.

    Args:
        day: Target day — 'today', 'tomorrow', or a weekday name like 'Monday'.
    """
    weekday = _resolve_weekday(day)
    tasks = get_tasks_for_day(weekday)

    if not tasks:
        return f"No tasks found for {weekday}."

    lines = [f"Tasks for {weekday} ({len(tasks)} total):\n"]
    for t in tasks:
        pin = " [Pinned]" if t["weekday"] == "Pinned" else ""
        lines.append(f"  [{t['status']}] {t['name']}{pin}")

    return "\n".join(lines)


@mcp.tool()
def plan_day(day: str) -> str:
    """
    Generate an AI-optimized daily schedule from your Notion tasks.
    Returns a preview of the proposed schedule. Use apply_schedule() to write it to Notion.

    Args:
        day: Target day — 'today', 'tomorrow', or a weekday name like 'Monday'.
    """
    global _pending_schedule

    weekday = _resolve_weekday(day)
    tasks = get_tasks_for_day(weekday)

    if not tasks:
        return f"No tasks found for {weekday}. Nothing to schedule."

    current = get_current_schedule()
    schedule = generate_schedule(tasks, current_schedule=current if current else None)
    _pending_schedule = schedule

    preview = format_schedule_preview(schedule)
    task_count = len(tasks)

    return (
        f"Proposed schedule for {weekday} ({task_count} tasks):\n\n"
        f"{preview}\n\n"
        f"Call apply_schedule() to write this to Notion, "
        f"or call plan_day('{day}') again to regenerate."
    )


@mcp.tool()
def apply_schedule() -> str:
    """
    Write the most recently generated schedule to Notion's Schedule Today table.
    Must call plan_day() first to generate a schedule.
    """
    global _pending_schedule

    if not _pending_schedule:
        return "No pending schedule. Call plan_day() first to generate one."

    result = write_schedule(_pending_schedule)
    applied = _pending_schedule
    _pending_schedule = []
    return f"{result} Wrote {len(applied)} time slots to Notion."


def main():
    mcp.run()


if __name__ == "__main__":
    main()
