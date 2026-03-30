import os
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NOTION_TASKS_DB_ID = os.environ["NOTION_TASKS_DB_ID"]
NOTION_SCHEDULE_PAGE_ID = os.environ["NOTION_SCHEDULE_PAGE_ID"]

PRIORITY_ORDER = [
    "Imp Urg",
    "Urg ~Imp",
    "Imp ~Urg",
    "In Progress",
    "~Imp ~Urg",
    "Note",
]

EXCLUDED_STATUSES = {"Done", "Cancelled", "Postponed"}

WEEKDAY_MAP = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

TIME_SLOTS: list[str] = []
for hour in range(6, 24):
    TIME_SLOTS.append(f"{hour}:00")
    TIME_SLOTS.append(f"{hour}:30")
