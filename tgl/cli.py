"""CLI for Toggl timer operations."""

import datetime
import json
import subprocess
import tomllib
from pathlib import Path

import click

from tgl.api import TogglAPI
from tgl.config import get_presets, init_config
from tgl.reporting import (
    REPORT_PERIODS,
    REPORTS_FILE,
    format_report_duration,
    import_legacy_report_set,
    load_report_sets,
    parse_report_date_range,
    parse_report_period,
    total_seconds_from_csv,
    write_report_sets,
)


@click.group()
@click.option(
    "--apitoken", envvar="TOGGL_API_TOKEN", default=None, help="Toggl API token"
)
@click.pass_context
def main(ctx, apitoken):
    """Toggl timer CLI."""
    ctx.ensure_object(dict)
    ctx.obj["api"] = None
    ctx.obj["apitoken"] = apitoken


def _get_api(ctx):
    """Return a lazily initialized API client."""
    api = ctx.obj.get("api")
    if api is None:
        try:
            api = TogglAPI(api_token=ctx.obj.get("apitoken"))
        except (ValueError, FileNotFoundError, OSError) as e:
            raise click.ClickException(str(e)) from e
        ctx.obj["api"] = api
    return api


@main.command()
@click.argument("description", required=False)
@click.option("--preset", "-P", default=None, help="Use a named preset")
@click.option("--project", "-p", type=int, default=None, help="Project ID")
@click.option("--tag", "-t", multiple=True, help="Tags")
@click.option(
    "--start-time",
    "-s",
    default=None,
    help="Start time (e.g. '5:45' or '2026-03-17T05:45')",
)
@click.pass_context
def start(ctx, description, preset, project, tag, start_time):
    """Start a new timer.

    With no arguments, enters interactive mode to pick a preset and description.
    """
    api = _get_api(ctx)
    wid = api.get_workspace_id()

    if preset:
        project, preset_tags, preset_name = _resolve_preset(preset)
        if not tag:
            tag = preset_tags
    elif description is None and not project:
        description, project, tag, preset_name = _interactive_start()
    else:
        preset_name = None

    if description is None:
        description = click.prompt("Description")

    start_utc = _parse_start_time(start_time) if start_time else None
    tags = list(tag) if tag else None
    entry = api.start_timer(
        description, wid, project_id=project, tags=tags, start_time=start_utc
    )

    parts = [f"Started: {description}"]
    if preset_name:
        parts.append(f"[{preset_name}]")
    click.echo(" ".join(parts))


def _resolve_preset(name):
    """Look up a preset by name. Returns (project_id, tags, preset_display_name)."""
    presets = get_presets()
    if name not in presets:
        available = ", ".join(sorted(presets.keys())) or "(none — run tgl init)"
        raise click.ClickException(f"Unknown preset '{name}'. Available: {available}")
    p = presets[name]
    return p["project_id"], p.get("tags", []), p.get("project_name", name)


def _interactive_start():
    """Prompt user to pick a preset and enter a description."""
    presets = get_presets()

    if not presets:
        description = click.prompt("Description")
        return description, None, (), None

    preset_list = list(presets.items())
    click.echo("Presets:")
    for i, (key, p) in enumerate(preset_list, 1):
        display = p.get("project_name", key)
        tags = p.get("tags", [])
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        click.echo(f"  {i}. {key:20s} {display}{tag_str}")

    choice = click.prompt("Preset #", type=int)
    if choice < 1 or choice > len(preset_list):
        raise click.ClickException(f"Invalid choice: {choice}")

    key, p = preset_list[choice - 1]
    description = click.prompt("Description")
    return (
        description,
        p["project_id"],
        p.get("tags", []),
        p.get("project_name", key),
    )


@main.command()
@click.pass_context
def resume(ctx):
    """Resume the last timer."""
    api = _get_api(ctx)

    current = api.current_timer()
    if current is not None:
        desc = current.get("description", "(no description)")
        click.echo(f"Timer already running: {desc}")
        return

    entries = api.recent_entries()
    # Find the first entry with a description
    entry = next((e for e in entries if e.get("description")), None)
    if entry is None:
        click.echo("No recent entries to resume")
        return

    wid = api.get_workspace_id()
    desc = entry["description"]
    project_id = entry.get("project_id")
    tags = entry.get("tags") or None
    api.start_timer(desc, wid, project_id=project_id, tags=tags)
    click.echo(f"Resumed: {desc}")


@main.command()
@click.pass_context
def stop(ctx):
    """Stop the current timer."""
    api = _get_api(ctx)
    entry = api.stop_timer()
    if entry is None:
        click.echo("No timer running")
        return
    desc = entry.get("description", "(no description)")
    duration = entry.get("duration", 0)
    click.echo(f"Stopped: {desc} ({_format_duration(duration)})")


@main.command()
@click.pass_context
def status(ctx):
    """Show the current timer status."""
    api = _get_api(ctx)
    entry = api.current_timer()
    if entry is None:
        click.echo("No timer running")
        return
    desc = entry.get("description", "(no description)")
    start_str = entry.get("start", "")
    elapsed = _elapsed_since(start_str)
    click.echo(f"Running: {desc} ({elapsed})")


PERIODS = ["today", "week", "last-week", "month"]
REPORT_DATE_RANGE_HELP = "Date range as START:END (overrides PERIOD)."


@main.command()
@click.argument(
    "period", default="today", type=click.Choice(PERIODS, case_sensitive=False)
)
@click.pass_context
def summary(ctx, period):
    """Show time summary for a period.

    PERIOD: today (default), week, last-week, month.
    """
    api = _get_api(ctx)
    wid = api.get_workspace_id()
    today = datetime.date.today()
    start_date, end_date = _date_range(period, today)

    entries = api.time_entries_between(start_date, end_date)
    # For running timers (negative duration), compute elapsed time
    now = datetime.datetime.now(datetime.timezone.utc)
    for e in entries:
        if e.get("duration", 0) < 0 and e.get("start"):
            start_dt = datetime.datetime.fromisoformat(e["start"])
            e["duration"] = int((now - start_dt).total_seconds())

    if not entries:
        click.echo(f"No entries for {period} ({start_date} to {end_date})")
        return

    # Build project name map
    projects = api.get_projects(wid)
    proj_names = {p["id"]: p["name"] for p in projects}

    # Group by project
    by_project = {}
    for e in entries:
        pid = e.get("project_id")
        name = proj_names.get(pid, "(no project)")
        by_project.setdefault(name, 0)
        by_project[name] += e.get("duration", 0)

    total = sum(by_project.values())

    # Display
    label = (
        f"{period} ({start_date} to {end_date})"
        if start_date != end_date
        else f"{period} ({start_date})"
    )
    click.echo(label)
    click.echo()
    for name, secs in sorted(by_project.items(), key=lambda x: -x[1]):
        click.echo(f"  {name:30s} {_format_duration(secs)}")
    click.echo()
    click.echo(f"  {'Total':30s} {_format_duration(total)}")


def _parse_report_date_range_option(ctx, param, value):
    """Click callback for --range START:END."""
    if value is None:
        return None

    try:
        return parse_report_date_range(value)
    except ValueError as e:
        raise click.BadParameter(str(e)) from e


def _resolve_report_dates(period, date_range):
    """Resolve either PERIOD or --range into (start_date, end_date)."""
    if date_range is not None:
        return date_range
    return parse_report_period(period)


def _report_duration(
    api, workspace_id, start_date, end_date, client_ids=None, tag_ids=None
):
    """Fetch and format a report duration."""
    csv_text = api.summary_report_csv(
        workspace_id,
        start_date,
        end_date,
        client_ids=client_ids,
        tag_ids=tag_ids,
    )
    return format_report_duration(total_seconds_from_csv(csv_text))


def _load_report_set(report_file, set_name):
    """Load a named report set or raise a CLI-friendly error."""
    report_sets = _load_report_sets_for_cli(report_file)
    if not report_sets:
        raise click.ClickException(f"No report sets found in {report_file}")
    if set_name not in report_sets:
        available = ", ".join(sorted(report_sets.keys()))
        raise click.ClickException(
            f"Unknown report set '{set_name}'. Available: {available}"
        )
    return report_sets[set_name]


def _copy_report_durations(durations):
    """Copy tab-separated durations to the macOS clipboard."""
    try:
        subprocess.run(
            ["pbcopy"],
            input="\t".join(durations),
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise click.ClickException(
            "pbcopy not found; clipboard copy is only available on macOS"
        ) from e


def _load_report_sets_for_cli(report_file):
    """Load report sets and surface invalid TOML as a CLI error."""
    try:
        return load_report_sets(report_file)
    except tomllib.TOMLDecodeError as e:
        raise click.ClickException(f"Invalid report file {report_file}: {e}") from e
    except OSError as e:
        raise click.ClickException(f"Could not read report file {report_file}: {e}") from e


def _import_legacy_report_set_for_cli(path):
    """Import a legacy report definition with CLI-friendly errors."""
    try:
        return import_legacy_report_set(path)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid legacy report file {path}: {e}") from e
    except OSError as e:
        raise click.ClickException(
            f"Could not read legacy report file {path}: {e}"
        ) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e


@main.group()
def report():
    """Reporting helpers built on the Toggl Reports API."""


@report.command("total")
@click.argument(
    "period",
    default="last-week",
    type=click.Choice(REPORT_PERIODS, case_sensitive=False),
)
@click.option(
    "--range",
    "date_range",
    callback=_parse_report_date_range_option,
    help=REPORT_DATE_RANGE_HELP,
)
@click.option(
    "--client", "client_ids", multiple=True, type=int, help="Client ID filter"
)
@click.option("--tag", "tag_ids", multiple=True, type=int, help="Tag ID filter")
@click.pass_context
def report_total(ctx, period, date_range, client_ids, tag_ids):
    """Print a total duration for a filtered report query.

    Report weeks are Sunday-based (unlike 'tgl summary' which uses Monday).
    """
    api = _get_api(ctx)
    wid = api.get_workspace_id()
    start_date, end_date = _resolve_report_dates(period, date_range)
    duration = _report_duration(
        api,
        wid,
        start_date,
        end_date,
        client_ids=list(client_ids) or None,
        tag_ids=list(tag_ids) or None,
    )
    click.echo(duration)


@report.command("batch")
@click.argument("set_name")
@click.argument(
    "period",
    default="last-week",
    type=click.Choice(REPORT_PERIODS, case_sensitive=False),
)
@click.option(
    "--range",
    "date_range",
    callback=_parse_report_date_range_option,
    help=REPORT_DATE_RANGE_HELP,
)
@click.option(
    "--file",
    "report_file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help=f"Report definition file (default: {REPORTS_FILE}).",
)
@click.option(
    "--copy", is_flag=True, help="Copy tab-separated durations to the clipboard"
)
@click.pass_context
def report_batch(ctx, set_name, period, date_range, report_file, copy):
    """Print a named batch report from reports.toml.

    Report weeks are Sunday-based (unlike 'tgl summary' which uses Monday).
    """
    report_file = report_file or REPORTS_FILE
    report_set = _load_report_set(report_file, set_name)
    api = _get_api(ctx)
    wid = api.get_workspace_id()
    start_date, end_date = _resolve_report_dates(period, date_range)

    durations = []
    for entry in report_set.get("entries", []):
        duration = _report_duration(
            api,
            wid,
            start_date,
            end_date,
            client_ids=entry.get("clients"),
            tag_ids=entry.get("tags"),
        )
        durations.append(duration)
        click.echo(f"{entry['label']}, {duration}")

    if copy:
        _copy_report_durations(durations)


@report.command("import")
@click.option(
    "--name", "set_name", required=True, help="Report set name to create/update"
)
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option(
    "--file",
    "report_file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help=f"Destination report definition file (default: {REPORTS_FILE}).",
)
def report_import(set_name, path, report_file):
    """Import a legacy entries.json file."""
    report_file = report_file or REPORTS_FILE
    report_sets = _load_report_sets_for_cli(report_file)
    report_sets[set_name] = _import_legacy_report_set_for_cli(path)
    write_report_sets(report_file, report_sets)
    entry_count = len(report_sets[set_name].get("entries", []))
    click.echo(f"Imported {entry_count} entries into {set_name}: {report_file}")


def _date_range(period, ref=None):
    """Return (start_date, end_date) for a named period."""
    if ref is None:
        ref = datetime.date.today()
    if period == "today":
        return ref, ref
    elif period == "week":
        monday = ref - datetime.timedelta(days=ref.weekday())
        return monday, ref
    elif period == "last-week":
        monday = ref - datetime.timedelta(days=ref.weekday())
        prev_monday = monday - datetime.timedelta(days=7)
        prev_sunday = monday - datetime.timedelta(days=1)
        return prev_monday, prev_sunday
    elif period == "month":
        return ref.replace(day=1), ref
    else:
        raise click.ClickException(f"Unknown period: {period}")


@main.command(name="init")
@click.pass_context
def init_cmd(ctx):
    """Generate config from your Toggl workspace."""
    api = _get_api(ctx)
    path = init_config(api)
    click.echo(f"Config written to {path}")
    click.echo("Edit it to customize presets, then use: tgl start -P <preset> <desc>")


def _format_duration(seconds):
    """Format seconds into h:mm:ss."""
    if seconds < 0:
        return "running"
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _parse_start_time(value):
    """Parse a start time string into a UTC datetime.

    Accepts 'HH:MM' (today, local time) or an ISO datetime string.
    """
    local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    try:
        # Try HH:MM format (today, local time)
        t = datetime.datetime.strptime(value, "%H:%M")
        local_dt = datetime.datetime.combine(
            datetime.date.today(), t.time(), tzinfo=local_tz
        )
        return local_dt.astimezone(datetime.timezone.utc)
    except ValueError:
        pass
    # Try ISO format
    try:
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz)
        return dt.astimezone(datetime.timezone.utc)
    except ValueError:
        raise click.ClickException(
            f"Cannot parse start time: {value!r}. Use HH:MM or ISO format."
        )


def _elapsed_since(start_str):
    """Calculate elapsed time from ISO start string."""
    if not start_str:
        return "unknown"
    start = datetime.datetime.fromisoformat(start_str)
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - start
    return _format_duration(int(delta.total_seconds()))
