"""CLI for Toggl timer operations."""

import datetime

import click

from tgl.api import TogglAPI


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
@click.argument("description")
@click.option("--project", "-p", type=int, default=None, help="Project ID")
@click.option("--tag", "-t", multiple=True, help="Tags")
@click.pass_context
def start(ctx, description, project, tag):
    """Start a new timer."""
    api = ctx.obj["api"]
    wid = api.get_workspace_id()
    entry = api.start_timer(description, wid, project_id=project, tags=tag or None)
    click.echo(f"Started: {description} (id={entry['id']})")


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
