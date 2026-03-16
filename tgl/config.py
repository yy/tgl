"""Configuration and presets for tgl."""

import tomllib
from pathlib import Path

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
    """Generate config.toml by fetching projects and tags from Toggl."""
    wid = api.get_workspace_id()
    projects = api.get_projects(wid)
    tags = api.get_tags(wid)

    active_projects = [p for p in projects if p.get("active")]
    active_projects.sort(key=lambda p: p["name"].lower())

    lines = [
        "# tgl configuration",
        "# Generated from your Toggl workspace. Edit freely.",
        "",
        "# Available tags (for reference when editing presets):",
    ]
    for t in sorted(tags, key=lambda t: t["name"].lower()):
        lines.append(f"#   {t['name']}")

    lines.append("")
    lines.append("# Presets: named timer configurations for quick start.")
    lines.append("# Each preset needs at minimum a project_id.")
    lines.append("# tags is optional. description is an optional default.")
    lines.append("")

    for p in active_projects:
        key = _slugify(p["name"])
        lines.append(f"[presets.{key}]")
        lines.append(f"project_id = {p['id']}")
        lines.append(f'project_name = "{p["name"]}"')
        lines.append("tags = []")
        lines.append("")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text("\n".join(lines) + "\n")
    return CONFIG_FILE


def _slugify(name):
    """Turn a project name into a TOML key."""
    return name.lower().replace(" ", "-").replace("/", "-")
