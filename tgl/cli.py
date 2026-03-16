"""CLI for Toggl timer operations."""

import datetime

import click

from tgl.api import TogglAPI
from tgl.config import get_presets, init_config


@click.group()
@click.option(
    "--apitoken", envvar="TOGGL_API_TOKEN", default=None, help="Toggl API token"
)
@click.pass_context
def main(ctx, apitoken):
    """Toggl timer CLI."""
    ctx.ensure_object(dict)
    ctx.obj["api"] = TogglAPI(api_token=apitoken)


@main.command()
@click.argument("description", required=False)
@click.option("--preset", "-P", default=None, help="Use a named preset")
@click.option("--project", "-p", type=int, default=None, help="Project ID")
@click.option("--tag", "-t", multiple=True, help="Tags")
@click.pass_context
def start(ctx, description, preset, project, tag):
    """Start a new timer.

    With no arguments, enters interactive mode to pick a preset and description.
    """
    api = ctx.obj["api"]
    wid = api.get_workspace_id()

    if preset:
        project, tag, preset_name = _resolve_preset(preset)
    elif description is None and not project:
        description, project, tag, preset_name = _interactive_start()
    else:
        preset_name = None

    if description is None:
        description = click.prompt("Description")

    tags = list(tag) if tag else None
    entry = api.start_timer(description, wid, project_id=project, tags=tags)

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
    api = ctx.obj["api"]

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
    api = ctx.obj["api"]
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
    api = ctx.obj["api"]
    entry = api.current_timer()
    if entry is None:
        click.echo("No timer running")
        return
    desc = entry.get("description", "(no description)")
    start_str = entry.get("start", "")
    elapsed = _elapsed_since(start_str)
    click.echo(f"Running: {desc} ({elapsed})")


PERIODS = ["today", "week", "last-week", "month"]


@main.command()
@click.argument(
    "period", default="today", type=click.Choice(PERIODS, case_sensitive=False)
)
@click.pass_context
def summary(ctx, period):
    """Show time summary for a period.

    PERIOD: today (default), week, last-week, month.
    """
    api = ctx.obj["api"]
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
    api = ctx.obj["api"]
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


def _elapsed_since(start_str):
    """Calculate elapsed time from ISO start string."""
    if not start_str:
        return "unknown"
    start = datetime.datetime.fromisoformat(start_str)
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - start
    return _format_duration(int(delta.total_seconds()))
