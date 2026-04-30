#!/usr/bin/env python3
"""Extract TS60 Trifecta schedule data from the source workbooks and PDFs."""

from __future__ import annotations

import argparse
import json
import re
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import openpyxl
from pypdf import PdfReader


SOURCE_META: dict[str, dict[str, str]] = {
    "3xTS60_Dec24v2.xlsx": {
        "title": "TS60 Trifecta December 2024",
        "period": "2024-12",
        "category": "trifecta",
    },
    "Stride_12-07-24.xlsx": {
        "title": "Stride December 7, 2024",
        "period": "2024-12",
        "category": "stride",
        "scheduledDate": "2024-12-07",
    },
    "3xTS60_JanFeb 25.xlsx": {
        "title": "Winter TS60 Trifecta January-February 2025",
        "period": "2025-01",
        "category": "trifecta",
    },
    "TS60 Trifecta_March 2025.xlsx": {
        "title": "TS60 Trifecta March 2025",
        "period": "2025-03",
        "category": "trifecta",
    },
    "TS60 Trifecta_April 2025.xlsx": {
        "title": "TS60 Trifecta April 2025",
        "period": "2025-04",
        "category": "trifecta",
    },
    "TS60 Trifecta_May 2025.pdf": {
        "title": "TS60 Trifecta May 2025",
        "period": "2025-05",
        "category": "trifecta",
    },
    "TS60 Trifecta_June 2025.xlsx": {
        "title": "TS60 Trifecta June 2025",
        "period": "2025-06",
        "category": "trifecta",
    },
    "TS60 Trifecta_Jul2025.pdf": {
        "title": "TS60 Trifecta July 2025",
        "period": "2025-07",
        "category": "trifecta",
    },
    "TS60 Trifecta_Aug 2025.xlsx": {
        "title": "TS60 Trifecta August 2025",
        "period": "2025-08",
        "category": "trifecta",
    },
    "COREvember 2025.xlsx": {
        "title": "COREvember 2025",
        "period": "2025-11",
        "category": "core",
    },
    "Sleigh Your Core_Dec 2025.xlsx": {
        "title": "Sleigh Your Core December 2025",
        "period": "2025-12",
        "category": "core",
    },
    "TS60 Trifecta_December 2025.xlsx": {
        "title": "TS60 Trifecta December 2025",
        "period": "2025-12",
        "category": "trifecta",
    },
    "TS60 Trifecta January 2026.xlsx": {
        "title": "TS60 Trifecta January 2026",
        "period": "2026-01",
        "category": "trifecta",
    },
    "Core_Feb 2026.xlsx": {
        "title": "February 2026 10 Minute Core",
        "period": "2026-02",
        "category": "core",
    },
    "TS60 Trifecta_Feb 2026.xlsx": {
        "title": "TS60 Trifecta February 2026",
        "period": "2026-02",
        "category": "trifecta",
    },
    "Core_March 2026.xlsx": {
        "title": "March 2026 10 Minute Core",
        "period": "2026-03",
        "category": "core",
    },
    "Trifecta_March 2026.xlsx": {
        "title": "TS60 Trifecta March 2026",
        "period": "2026-03",
        "category": "trifecta",
    },
    "April \u201826 Trifecta.xlsx": {
        "title": "TS60 Trifecta April 2026",
        "period": "2026-04",
        "category": "trifecta",
    },
}


TITLE_WORDS = ("trifecta", "ts60", "corevember", "sleigh your core")
SKIPPED_GROUP_TITLES = {"Option A: Doing TS60 Live"}
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
WEEK_RE = re.compile(r"\bweek\s*(\d+)\b", re.IGNORECASE)
DAY_RE = re.compile(r"\bday\s*(\d+)\b", re.IGNORECASE)
LEADING_WEEK_RE = re.compile(r"^\s*(\d+)")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "schedule"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return " ".join(str(value).replace("\u2018", "'").replace("\u2019", "'").split())


def clean_workout_title(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"\s*[-\u2013\u2014]?\s*\bW\d+(?:D\d+)?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,)])", r"\1", text)
    return text.strip(" -")


def is_blank(value: Any) -> bool:
    return value is None or clean_text(value) == ""


def parse_leading_week(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = clean_text(value)
    week_match = WEEK_RE.search(text)
    if week_match:
        return int(week_match.group(1))
    leading = LEADING_WEEK_RE.match(text)
    if leading:
        return int(leading.group(1))
    return None


def parse_day(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    match = DAY_RE.search(clean_text(value))
    if match:
        return int(match.group(1))
    return None


def parse_display_date(text: str) -> dict[str, str | None]:
    match = None
    for match in DATE_RE.finditer(text):
        pass
    if not match:
        return {"classDate": None, "classDateDisplay": None}

    month, day, year = match.groups()
    year_number = int(year)
    if year_number < 100:
        year_number += 2000

    try:
        parsed = date(year_number, int(month), int(day))
    except ValueError:
        return {"classDate": None, "classDateDisplay": match.group(0)}

    return {
        "classDate": parsed.isoformat(),
        "classDateDisplay": f"{int(month)}/{int(day)}/{str(year_number)[-2:]}",
    }


def parse_duration(text: str) -> str | None:
    match = re.search(r"\b(\d{1,3})\s*min\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} min"
    if "ts60" in text.lower() or "total strength" in text.lower():
        return "60 min"
    return None


def infer_workout_type(text: str, category: str) -> str:
    lowered = text.lower()
    if category == "core":
        return "Core"
    if category == "stride":
        if "hike" in lowered:
            return "Hike"
        if "walk + run" in lowered:
            return "Walk + Run"
        if "walk" in lowered:
            return "Walk"
        if "run" in lowered:
            return "Run"
        return "Stride"
    if "stretch" in lowered:
        return "Stretch"
    if "mobility" in lowered:
        return "Mobility"
    if "ts30" in lowered:
        return "TS30"
    if "ts60" in lowered or "total strength" in lowered:
        return "TS60"
    if "core" in lowered:
        return "Core"
    return "Strength"


def group_title_to_id(schedule_id: str, title: str) -> str:
    return f"{schedule_id}-{slugify(title)}"


def make_entry(
    *,
    schedule_id: str,
    group_id: str,
    group_title: str,
    source_file: str,
    source_cell: str,
    category: str,
    workout: str,
    url: str | None = None,
    week: int | None = None,
    day: int | None = None,
    day_label: str | None = None,
    scheduled_date: str | None = None,
    start_time: str | None = None,
    stop_time: str | None = None,
    instructor: str | None = None,
    notes: str | None = None,
    sequence: int = 0,
) -> dict[str, Any]:
    workout = clean_workout_title(workout)
    parsed_date = parse_display_date(workout)
    link_status = "available" if url else "missing"
    if notes and "tbd" in notes.lower():
        link_status = "tbd"

    return {
        "id": f"{schedule_id}-{slugify(group_title)}-{sequence:03d}",
        "scheduleId": schedule_id,
        "groupId": group_id,
        "groupTitle": group_title,
        "sourceFile": source_file,
        "week": week,
        "day": day,
        "dayLabel": day_label,
        "scheduledDate": scheduled_date,
        "startTime": start_time,
        "stopTime": stop_time,
        "instructor": instructor,
        "workout": workout,
        "workoutType": infer_workout_type(workout, category),
        "duration": parse_duration(workout),
        "classDate": parsed_date["classDate"],
        "classDateDisplay": parsed_date["classDateDisplay"],
        "url": url,
        "linkStatus": link_status,
        "notes": notes,
    }


def normalize_group_title(value: str) -> str:
    text = clean_text(value).strip(":")
    if text.upper().startswith("OPTION A"):
        return "Option A: Doing TS60 Live"
    if text.upper().startswith("OPTION B"):
        return "Main Schedule"
    return text or "Main Schedule"


def get_or_create_group(schedule: dict[str, Any], title: str) -> dict[str, Any]:
    normalized = normalize_group_title(title)
    for group in schedule["groups"]:
        if group["title"] == normalized:
            return group
    group = {
        "id": group_title_to_id(schedule["id"], normalized),
        "title": normalized,
        "entries": [],
    }
    schedule["groups"].append(group)
    return group


def hyperlink_target(cell: Any) -> str | None:
    if not getattr(cell, "hyperlink", None):
        return None
    return cell.hyperlink.target or cell.hyperlink.location


def format_time_value(value: Any) -> str | None:
    if isinstance(value, time):
        hour = value.hour
        minute = value.minute
    elif isinstance(value, datetime):
        hour = value.hour
        minute = value.minute
    else:
        return None

    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix}"


def make_schedule(path: Path, meta: dict[str, str]) -> dict[str, Any]:
    return {
        "id": slugify(meta["title"]),
        "title": meta["title"],
        "period": meta["period"],
        "year": meta["period"][:4],
        "category": meta["category"],
        "sourceFile": path.name,
        "sourceFormat": path.suffix.lower().lstrip("."),
        "groups": [],
    }


def looks_like_title_row(values: list[Any]) -> bool:
    texts = [clean_text(value).lower() for value in values if not is_blank(value)]
    if len(texts) != 1:
        return False
    return any(word in texts[0] for word in TITLE_WORDS)


def looks_like_note_row(text: str) -> bool:
    lowered = text.lower()
    return lowered.startswith(("note", "ultimately")) or "order of classes" in lowered


def find_first_value(cells: list[Any], start: int) -> tuple[int | None, str | None]:
    for index in range(start, len(cells)):
        if not is_blank(cells[index].value):
            return index, clean_text(cells[index].value)
    return None, None


def add_entry_to_group(
    schedule: dict[str, Any],
    group: dict[str, Any],
    **kwargs: Any,
) -> None:
    entry = make_entry(
        schedule_id=schedule["id"],
        group_id=group["id"],
        group_title=group["title"],
        source_file=schedule["sourceFile"],
        category=schedule["category"],
        sequence=len(group["entries"]) + 1,
        **kwargs,
    )
    if entry["workout"]:
        group["entries"].append(entry)


def extract_xlsx(path: Path, meta: dict[str, str]) -> dict[str, Any]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    schedule = make_schedule(path, meta)
    group = get_or_create_group(schedule, "Main Schedule")
    current_week: int | None = None
    mode = "unknown"

    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            values = [cell.value for cell in row]
            if all(is_blank(value) for value in values):
                continue

            first_text = clean_text(values[0]).lower() if values else ""
            normalized_first = clean_text(values[0]) if values else ""

            if first_text.startswith("option "):
                group = get_or_create_group(schedule, normalized_first)
                current_week = None
                mode = "unknown"
                continue

            lowered_cells = [clean_text(value).lower() for value in values]
            if looks_like_title_row(values):
                continue

            if "date" in lowered_cells[:2] and any("class" in text for text in lowered_cells[:4]):
                mode = "date"
                continue

            if {"start (est)", "stop (est)", "type", "class"}.issubset(set(lowered_cells[:5])):
                mode = "time_block"
                continue

            if mode == "time_block":
                workout = clean_text(values[3] if len(values) > 3 else None)
                if not workout or workout.lower() == "break":
                    continue
                url = hyperlink_target(row[5]) if len(row) > 5 else None
                class_type = clean_text(values[2] if len(values) > 2 else None)
                instructor = clean_text(values[4] if len(values) > 4 else None) or None
                start_time = format_time_value(values[0])
                stop_time = format_time_value(values[1])
                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[3].coordinate}",
                    workout=workout,
                    url=url,
                    scheduled_date=meta.get("scheduledDate"),
                    start_time=start_time,
                    stop_time=stop_time,
                    instructor=instructor,
                    notes=class_type or None,
                )
                continue

            is_week_header = first_text in {"week", "week/day"}
            is_week_header = is_week_header or (
                first_text.startswith("week") and parse_leading_week(values[0]) is None
            )
            if is_week_header:
                mode = "week_day_class" if any("day" in text for text in lowered_cells[:3]) else "week_class"
                continue

            if schedule["category"] == "core" or mode == "date" or isinstance(values[0], (datetime, date)):
                scheduled = values[0]
                scheduled_date = None
                week = None
                day = None
                if isinstance(scheduled, datetime):
                    scheduled_date = scheduled.date().isoformat()
                    week = math.ceil(scheduled.day / 7)
                    day = scheduled.day
                elif isinstance(scheduled, date):
                    scheduled_date = scheduled.isoformat()
                    week = math.ceil(scheduled.day / 7)
                    day = scheduled.day
                class_col, workout = find_first_value(row, 1)
                if not workout:
                    continue
                notes = " ".join(
                    clean_text(cell.value)
                    for cell in row[2:]
                    if not is_blank(cell.value) and clean_text(cell.value).lower() != workout.lower()
                ) or None
                url = hyperlink_target(row[class_col]) if class_col is not None else None
                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[class_col].coordinate if class_col is not None else row[0].coordinate}",
                    workout=workout,
                    url=url,
                    week=week,
                    day=day,
                    day_label=f"Day {day}" if day else None,
                    scheduled_date=scheduled_date,
                    notes=notes,
                )
                continue

            if (
                mode == "week_day_class"
                and parse_leading_week(values[0]) is not None
                and parse_day(values[1]) is not None
            ):
                week = parse_leading_week(values[0])
                day = parse_day(values[1])
                class_col, workout = find_first_value(row, 2)
                if not workout:
                    continue
                current_week = week
                url = hyperlink_target(row[class_col]) if class_col is not None else None
                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[class_col].coordinate if class_col is not None else row[0].coordinate}",
                    workout=workout,
                    url=url,
                    week=week,
                    day=day,
                    day_label=f"Day {day}" if day else None,
                )
                continue

            week_from_first = parse_leading_week(values[0])
            if week_from_first is not None:
                current_week = week_from_first
                if DAY_RE.search(normalized_first):
                    day = parse_day(normalized_first)
                    day_label = normalized_first
                    class_col, workout = find_first_value(row, 1)
                else:
                    day = parse_day(values[1])
                    day_label = f"Day {day}" if day and mode == "week_day_class" else None
                    class_col, workout = find_first_value(row, 1)

                if not workout:
                    continue

                url = hyperlink_target(row[class_col]) if class_col is not None else None
                link_note = None
                if class_col is not None:
                    for candidate in row[class_col + 1 :]:
                        candidate_text = clean_text(candidate.value)
                        if candidate_text and candidate_text.lower() in {"link", "tbd"}:
                            link_note = candidate_text
                            url = url or hyperlink_target(candidate)
                            break

                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[class_col].coordinate if class_col is not None else row[0].coordinate}",
                    workout=workout,
                    url=url,
                    week=week_from_first,
                    day=day,
                    day_label=day_label,
                    notes=link_note,
                )
                continue

            day = parse_day(values[0])
            if current_week is not None and day is not None:
                class_col, workout = find_first_value(row, 1)
                if not workout:
                    continue
                url = hyperlink_target(row[class_col]) if class_col is not None else None
                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[class_col].coordinate if class_col is not None else row[0].coordinate}",
                    workout=workout,
                    url=url,
                    week=current_week,
                    day=day,
                    day_label=normalized_first,
                )
                continue

            # Some sheets use a single trailing row as an extra option for the
            # previous week, for example an advanced alternate class.
            class_col, workout = find_first_value(row, 0)
            if (
                current_week is not None
                and workout
                and not looks_like_title_row(values)
                and not looks_like_note_row(workout)
            ):
                url = hyperlink_target(row[class_col]) if class_col is not None else None
                add_entry_to_group(
                    schedule,
                    group,
                    source_cell=f"{worksheet.title}!{row[class_col].coordinate if class_col is not None else row[0].coordinate}",
                    workout=workout,
                    url=url,
                    week=current_week,
                )

    schedule["groups"] = [
        item for item in schedule["groups"] if item["entries"] and item["title"] not in SKIPPED_GROUP_TITLES
    ]
    return schedule


def normalize_pdf_workout(text: str) -> str:
    replacements = {
        "11/10/2 4": "11/10/24",
        "7/6/2-5": "7/6/25",
        "Z/.6/.25": "7/6/25",
        "7/2Q/25": "7/20/25",
    }
    text = clean_text(text)
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def extract_pdf(path: Path, meta: dict[str, str]) -> dict[str, Any]:
    schedule = make_schedule(path, meta)
    group = get_or_create_group(schedule, "Main Schedule")
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows: list[tuple[int, str]] = []

    if lines[:1] == ["Week"] and "Class" in lines:
        class_index = lines.index("Class")
        week_values = [int(line) for line in lines[1:class_index] if line.isdigit()]
        class_values = [normalize_pdf_workout(line) for line in lines[class_index + 1 :]]
        rows = list(zip(week_values, class_values, strict=False))
    else:
        for line in lines:
            if line.lower().startswith("week"):
                continue
            match = re.match(r"^(\d+)\s+(.+)$", line)
            if match:
                rows.append((int(match.group(1)), normalize_pdf_workout(match.group(2))))

    for index, (week, workout) in enumerate(rows, start=1):
        add_entry_to_group(
            schedule,
            group,
            source_cell=f"PDF row {index}",
            workout=workout,
            week=week,
        )

    schedule["groups"] = [item for item in schedule["groups"] if item["entries"]]
    return schedule


def collect_schedules(source_dir: Path) -> list[dict[str, Any]]:
    schedules: list[dict[str, Any]] = []
    for filename, meta in SOURCE_META.items():
        path = source_dir / filename
        if not path.exists():
            continue
        if path.suffix.lower() == ".xlsx":
            schedules.append(extract_xlsx(path, meta))
        elif path.suffix.lower() == ".pdf":
            schedules.append(extract_pdf(path, meta))
    return sorted(schedules, key=lambda item: (item["period"], item["title"]))


def flatten_entries(schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for schedule in schedules:
        for group in schedule["groups"]:
            for entry in group["entries"]:
                flat = {
                    "scheduleTitle": schedule["title"],
                    "schedulePeriod": schedule["period"],
                    "category": schedule["category"],
                    **entry,
                }
                entries.append(flat)
    return entries


def build_payload(source_dir: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        source_directory = str(source_dir.resolve().relative_to(repo_root))
    except ValueError:
        source_directory = str(source_dir)

    schedules = collect_schedules(source_dir)
    entries = flatten_entries(schedules)
    linked = sum(1 for entry in entries if entry.get("url"))
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceDirectory": source_directory,
        "stats": {
            "scheduleCount": len(schedules),
            "workoutCount": len(entries),
            "linkedWorkoutCount": linked,
            "sourceCount": len({schedule["sourceFile"] for schedule in schedules}),
        },
        "schedules": schedules,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "sources",
        help="Directory containing schedule source files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "schedules.json",
        help="JSON output path.",
    )
    args = parser.parse_args()

    payload = build_payload(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output} with {payload['stats']['scheduleCount']} schedules "
        f"and {payload['stats']['workoutCount']} workouts."
    )


if __name__ == "__main__":
    main()
