from notion_client import Client

from .config import (
    NOTION_API_KEY,
    NOTION_SCHEDULE_PAGE_ID,
    NOTION_TASKS_DB_ID,
    EXCLUDED_STATUSES,
    PRIORITY_ORDER,
)

notion = Client(auth=NOTION_API_KEY)


def _resolve_data_source_id(database_id: str) -> str:
    """Find the data_source ID for a given database ID (Notion API 2025+)."""
    results = notion.search(
        query="",
        filter={"value": "data_source", "property": "object"},
    )
    for r in results.get("results", []):
        parent = r.get("parent", {})
        if parent.get("database_id") == database_id:
            return r["id"]
    raise ValueError(
        f"No data source found for database {database_id}. "
        "Make sure the database is shared with your integration."
    )


_data_source_id_cache: dict[str, str] = {}


def _get_data_source_id(database_id: str) -> str:
    if database_id not in _data_source_id_cache:
        _data_source_id_cache[database_id] = _resolve_data_source_id(database_id)
    return _data_source_id_cache[database_id]


def get_tasks_for_day(weekday: str) -> list[dict]:
    """Query Upcoming Tasks DB for a given weekday + Pinned tasks, excluding completed ones."""
    ds_id = _get_data_source_id(NOTION_TASKS_DB_ID)
    response = notion.request(
        path=f"data_sources/{ds_id}/query",
        method="POST",
        body={
            "filter": {
                "and": [
                    {
                        "or": [
                            {"property": "Weekday", "select": {"equals": weekday}},
                            {"property": "Weekday", "select": {"equals": "Pinned"}},
                        ]
                    },
                    *[
                        {"property": "Status", "select": {"does_not_equal": s}}
                        for s in EXCLUDED_STATUSES
                    ],
                ]
            }
        },
    )

    tasks = []
    for page in response["results"]:
        props = page["properties"]

        title_parts = props.get("Task", {}).get("title", [])
        name = "".join(t.get("plain_text", "") for t in title_parts).strip()
        if not name:
            continue

        status_obj = props.get("Status", {}).get("select")
        status = status_obj["name"] if status_obj else "Unknown"

        weekday_obj = props.get("Weekday", {}).get("select")
        day = weekday_obj["name"] if weekday_obj else "Unknown"

        priority = PRIORITY_ORDER.index(status) if status in PRIORITY_ORDER else 99

        tasks.append({
            "name": name,
            "status": status,
            "weekday": day,
            "priority": priority,
            "page_id": page["id"],
        })

    tasks.sort(key=lambda t: t["priority"])
    return tasks


def _find_schedule_today_block() -> str | None:
    """Walk children of the schedule page to find the 'Schedule Today' toggle."""
    children = notion.blocks.children.list(block_id=NOTION_SCHEDULE_PAGE_ID)
    for block in children["results"]:
        block_type = block.get("type")
        if block_type in ("toggle", "heading_1", "heading_2", "heading_3"):
            texts = block.get(block_type, {}).get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in texts).strip()
            if "schedule today" in text.lower():
                return block["id"]
    return None


def _find_table_block(parent_block_id: str) -> str | None:
    """Find first table block among children of a given block."""
    children = notion.blocks.children.list(block_id=parent_block_id)
    for block in children["results"]:
        if block.get("type") == "table":
            return block["id"]
    return None


def get_current_schedule() -> list[list[str]]:
    """Read the current schedule table and return rows as lists of strings."""
    toggle_id = _find_schedule_today_block()
    if not toggle_id:
        return []

    table_id = _find_table_block(toggle_id)
    if not table_id:
        return []

    children = notion.blocks.children.list(block_id=table_id)
    rows = []
    for block in children["results"]:
        if block.get("type") != "table_row":
            continue
        cells = block["table_row"]["cells"]
        row = []
        for cell in cells:
            row.append("".join(t.get("plain_text", "") for t in cell).strip())
        rows.append(row)
    return rows


def _delete_block(block_id: str) -> None:
    notion.blocks.delete(block_id=block_id)


def write_schedule(slots: list[dict]) -> str:
    """
    Write a schedule to Notion under the 'Schedule Today' toggle.

    slots: list of dicts with 'time' (e.g. '7:00') and 'activity' keys.
    Rebuilds the 4-column table: [hour, activity, half-hour, activity].
    """
    toggle_id = _find_schedule_today_block()
    if not toggle_id:
        raise ValueError(
            "Could not find 'Schedule Today' toggle block. "
            "Make sure the page is shared with your integration."
        )

    old_table_id = _find_table_block(toggle_id)
    if old_table_id:
        _delete_block(old_table_id)

    slot_map: dict[str, str] = {}
    for s in slots:
        slot_map[s["time"]] = s["activity"]

    rows: list[dict] = []
    for hour in range(6, 24):
        h_key = f"{hour}:00"
        hh_key = f"{hour}:30"
        row = {
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"type": "text", "text": {"content": str(hour)}}],
                    [{"type": "text", "text": {"content": slot_map.get(h_key, "")}}],
                    [{"type": "text", "text": {"content": f"{hour}:30"}}],
                    [{"type": "text", "text": {"content": slot_map.get(hh_key, "")}}],
                ]
            },
        }
        rows.append(row)

    table_block = {
        "type": "table",
        "table": {
            "table_width": 4,
            "has_column_header": False,
            "has_row_header": False,
            "children": rows,
        },
    }

    notion.blocks.children.append(block_id=toggle_id, children=[table_block])
    return "Schedule written successfully."
