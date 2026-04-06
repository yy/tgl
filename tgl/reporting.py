"""Helpers for report-oriented Toggl workflows."""

import csv
import datetime
import json
import tomllib
from io import StringIO
from pathlib import Path

from tgl.config import CONFIG_DIR

REPORTS_FILE = CONFIG_DIR / "reports.toml"
REPORT_PERIODS = ["today", "this-week", "last-week", "month"]


def parse_report_period(period, ref=None):
    """Return a Sunday-based date range for report commands."""
    if ref is None:
        ref = datetime.date.today()

    if period == "today":
        return ref, ref
    if period == "this-week":
        return _current_week_start(ref), ref
    if period == "last-week":
        current_week_start = _current_week_start(ref)
        start = current_week_start - datetime.timedelta(days=7)
        end = current_week_start - datetime.timedelta(days=1)
        return start, end
    if period == "month":
        return ref.replace(day=1), ref

    raise ValueError(f"Unknown report period: {period}")


def parse_report_date_range(value):
    """Parse START:END into a pair of dates."""
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(
            f"Date range must be START:END (e.g. 2026-03-01:2026-03-07), got: {value}"
        )

    try:
        start = datetime.date.fromisoformat(parts[0].strip())
        end = datetime.date.fromisoformat(parts[1].strip())
    except ValueError:
        raise

    if start > end:
        raise ValueError("Start date must not be after end date")

    return start, end


def total_seconds_from_csv(csv_text):
    """Sum the Duration column from a Toggl CSV response."""
    # Defensive: API layer strips BOM from bytes, but callers may pass raw text
    csv_text = csv_text.lstrip("\ufeff")
    reader = csv.DictReader(StringIO(csv_text))

    if reader.fieldnames is None:
        return 0
    if "Duration" not in reader.fieldnames:
        raise ValueError("CSV is missing required Duration column")

    total = 0
    for row in reader:
        duration = (row.get("Duration") or "").strip()
        if not duration:
            continue
        total += _duration_to_seconds(duration)

    return total


def format_report_duration(seconds):
    """Format seconds into HH:MM:SS with a minimum two-digit hour field."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def load_report_sets(path=REPORTS_FILE):
    """Load report sets from reports.toml."""
    report_path = Path(path)
    if not report_path.exists():
        return {}

    with open(report_path, "rb") as f:
        config = tomllib.load(f)

    return config.get("report_sets", {})


def import_legacy_report_set(path):
    """Convert toggl-review entries.json into a single report set."""
    legacy_path = Path(path)
    with open(legacy_path) as f:
        entries = json.load(f)

    workspace_ids = {
        entry.get("params", {}).get("workspace_id")
        for entry in entries
        if entry.get("params", {}).get("workspace_id") is not None
    }
    if len(workspace_ids) > 1:
        raise ValueError("Legacy entries must target a single workspace")

    report_entries = []
    for entry in entries:
        params = entry.get("params", {})
        report_entry = {"label": entry["title"]}
        if params.get("client_ids"):
            report_entry["clients"] = list(params["client_ids"])
        if params.get("tag_ids"):
            report_entry["tags"] = list(params["tag_ids"])
        report_entries.append(report_entry)

    return {"entries": report_entries}


def write_report_sets(path, report_sets):
    """Write report sets to reports.toml."""
    report_path = Path(path)
    lines = ["# tgl report definitions", ""]

    for set_name, report_set in report_sets.items():
        key = _format_toml_key(set_name)
        lines.append(f"[report_sets.{key}]")
        lines.append("")

        for entry in report_set.get("entries", []):
            lines.append(f"[[report_sets.{key}.entries]]")
            lines.append(f'label = "{_escape_toml_string(entry["label"])}"')
            if "clients" in entry:
                lines.append(f"clients = [{_format_int_list(entry['clients'])}]")
            if "tags" in entry:
                lines.append(f"tags = [{_format_int_list(entry['tags'])}]")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n")


def _current_week_start(ref):
    """Return the Sunday that starts the current report week."""
    days_since_sunday = (ref.weekday() + 1) % 7
    return ref - datetime.timedelta(days=days_since_sunday)


def _duration_to_seconds(duration):
    parts = duration.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid duration: {duration}")

    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as e:
        raise ValueError(f"Invalid duration: {duration}") from e

    return hours * 3600 + minutes * 60 + seconds


def _format_int_list(values):
    return ", ".join(str(value) for value in values)


def _format_toml_key(value):
    return f'"{_escape_toml_string(value)}"'


def _escape_toml_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')
