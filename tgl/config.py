"""Configuration and presets for tgl."""

import tomllib
from pathlib import Path

import click

CONFIG_DIR = Path.home() / ".config" / "tgl"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def load_config():
    """Load config from ~/.config/tgl/config.toml, or empty dict."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def get_presets():
    """Return dict of preset name -> {project_id, tags, description}."""
    config = load_config()
    return config.get("presets", {})


def init_config(api):
    """Interactively generate config.toml from Toggl workspace."""
    wid = api.get_workspace_id()
    clients = api.get_clients(wid)
    projects = api.get_projects(wid)
    tags = api.get_tags(wid)

    client_names = {c["id"]: c["name"] for c in clients}
    active_projects = sorted(
        [p for p in projects if p.get("active")],
        key=lambda p: p["name"].lower(),
    )
    tag_list = sorted(tags, key=lambda t: t["name"].lower())

    # Step 1: Pick areas (clients)
    sorted_clients = sorted(clients, key=lambda c: c["name"].lower())
    click.echo("Areas (clients):")
    for i, c in enumerate(sorted_clients, 1):
        proj_count = sum(1 for p in active_projects if p.get("client_id") == c["id"])
        click.echo(f"  {i}. {c['name']} ({proj_count} active projects)")

    choice = _prompt_choices(
        "\nWhich areas? (numbers like 1,3,5 or 'all')", len(sorted_clients)
    )
    if choice is None:
        selected_clients = sorted_clients
    else:
        selected_clients = [sorted_clients[i] for i in choice]

    selected_client_ids = {c["id"] for c in selected_clients}

    # Filter projects to selected areas
    area_projects = sorted(
        [p for p in active_projects if p.get("client_id") in selected_client_ids],
        key=lambda p: p["name"].lower(),
    )

    if not area_projects:
        click.echo("No active projects in selected areas")
        return None

    # Step 2: Pick projects
    click.echo("\nProjects in selected areas:")
    for i, p in enumerate(area_projects, 1):
        area = client_names.get(p.get("client_id"), "")
        click.echo(f"  {i}. {p['name']} ({area})")

    choice = _prompt_choices(
        "\nWhich projects? (numbers like 1,3,5 or 'all')", len(area_projects)
    )
    if choice is None:
        selected = area_projects
    else:
        selected = [area_projects[i] for i in choice]

    if not selected:
        click.echo("No projects selected")
        return None

    # Step 3: Assign tags per project
    if tag_list:
        click.echo("\nAvailable tags:")
        for i, t in enumerate(tag_list, 1):
            click.echo(f"  {i}. {t['name']}")
        click.echo()

    presets = {}
    for p in selected:
        key = _slugify(p["name"])
        preset = {"project_id": p["id"], "project_name": p["name"], "tags": []}

        if tag_list:
            tag_choice = click.prompt(
                f"Tags for {p['name']}? (numbers like 1,2 or enter to skip)",
                default="",
                show_default=False,
            )
            if tag_choice.strip():
                tag_indices = [
                    int(x.strip()) for x in tag_choice.split(",") if x.strip().isdigit()
                ]
                preset["tags"] = [
                    tag_list[i - 1]["name"]
                    for i in tag_indices
                    if 1 <= i <= len(tag_list)
                ]

        presets[key] = preset

    # Step 4: Show summary
    click.echo("\nSummary:")
    for key, p in presets.items():
        tags_str = ", ".join(p["tags"]) if p["tags"] else "(none)"
        area = client_names.get(
            next(
                (
                    proj.get("client_id")
                    for proj in selected
                    if proj["id"] == p["project_id"]
                ),
                None,
            ),
            "",
        )
        click.echo(f"  {p['project_name']} ({area}) -> tags: {tags_str}")

    # Write config
    _write_config(presets, tag_list)
    return CONFIG_FILE


def _prompt_choices(prompt_text, total):
    """Prompt for comma-separated numbers or 'all'. Returns list of 0-based indices or None for all."""
    choice = click.prompt(prompt_text, default="all")
    if choice.strip().lower() == "all":
        return None
    indices = [int(x.strip()) for x in choice.split(",") if x.strip().isdigit()]
    return [i - 1 for i in indices if 1 <= i <= total]


def _write_config(presets, tag_list):
    """Write presets to config.toml."""
    lines = [
        "# tgl configuration",
        "# Generated from your Toggl workspace. Edit freely.",
        "",
        "# Available tags (for reference when editing presets):",
    ]
    for t in tag_list:
        lines.append(f"#   {t['name']}")

    lines.append("")

    for key, p in presets.items():
        lines.append(f"[presets.{key}]")
        lines.append(f"project_id = {p['project_id']}")
        lines.append(f'project_name = "{p["project_name"]}"')
        tag_str = ", ".join(f'"{t}"' for t in p.get("tags", []))
        lines.append(f"tags = [{tag_str}]")
        lines.append("")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text("\n".join(lines) + "\n")


def _slugify(name):
    """Turn a project name into a TOML key."""
    return name.lower().replace(" ", "-").replace("/", "-")
