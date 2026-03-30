import sys
import json
from datetime import datetime, timedelta

from .config import WEEKDAY_MAP
from .notion_ops import get_tasks_for_day, get_tasks_with_details, get_current_schedule, write_schedule
from .scheduler import generate_schedule, format_schedule_preview


def resolve_weekday(target: str) -> str:
    target = target.strip().lower()
    if target == "today":
        return WEEKDAY_MAP[datetime.now().weekday()]
    if target == "tomorrow":
        tomorrow = datetime.now() + timedelta(days=1)
        return WEEKDAY_MAP[tomorrow.weekday()]
    for name in WEEKDAY_MAP.values():
        if target == name.lower():
            return name
    print(f"Unknown day: '{target}'. Use 'today', 'tomorrow', or a weekday name.")
    sys.exit(1)


def cmd_tasks(day: str):
    weekday = resolve_weekday(day)
    tasks = get_tasks_for_day(weekday)
    if not tasks:
        print(f"No tasks found for {weekday}.")
        return
    print(f"\nTasks for {weekday} ({len(tasks)} total):\n")
    for t in tasks:
        pin = " [Pinned]" if t["weekday"] == "Pinned" else ""
        print(f"  [{t['status']:>10}]  {t['name']}{pin}")
    print()


def cmd_plan(day: str):
    weekday = resolve_weekday(day)
    tasks = get_tasks_with_details(weekday)
    if not tasks:
        print(f"No tasks found for {weekday}. Nothing to schedule.")
        return

    print(f"\nFound {len(tasks)} tasks for {weekday}. Generating schedule...\n")

    current = get_current_schedule()
    schedule = generate_schedule(tasks, current_schedule=current if current else None)

    print("Proposed schedule:\n")
    print(format_schedule_preview(schedule))
    print()

    answer = input("Write this schedule to Notion? [y/N] ").strip().lower()
    if answer in ("y", "yes"):
        result = write_schedule(schedule)
        print(f"\n{result}")
    else:
        print("\nSchedule discarded.")

    dump = input("Save schedule to JSON file? [y/N] ").strip().lower()
    if dump in ("y", "yes"):
        filename = f"schedule_{weekday.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(schedule, f, indent=2)
        print(f"Saved to {filename}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.cli tasks <day>    List tasks for a day")
        print("  python -m src.cli plan <day>     Generate & apply schedule")
        print()
        print("  <day> = 'today', 'tomorrow', or a weekday name like 'Monday'")
        sys.exit(0)

    command = sys.argv[1].lower()
    day = sys.argv[2] if len(sys.argv) > 2 else "tomorrow"

    if command == "tasks":
        cmd_tasks(day)
    elif command == "plan":
        cmd_plan(day)
    else:
        print(f"Unknown command: '{command}'. Use 'tasks' or 'plan'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
