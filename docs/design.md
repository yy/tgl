# Design Principles

## Philosophy

tgl exists because switching to a browser to press a button breaks flow. A timer should be as easy to start as typing a command. It also serves as a tool that AI agents (e.g., Claude Code) can invoke to track time on your behalf as part of automated workflows.

## Principles

### Do one thing

tgl manages the current timer: start, stop, status, resume. It does not sync reports, manage projects, or replicate the Toggl web UI. If you need those, use the web app.

### Clear errors

- Missing token: tell the user where to put it and where to find it.
- No timer running on `stop`: say so and exit cleanly.
- API errors surface the HTTP status directly.

### Token resolution chain

Tokens are resolved in priority order, giving users flexibility without complexity:

1. `--apitoken` flag (explicit, for scripts and one-offs)
2. `TOGGL_API_TOKEN` environment variable (for shell/direnv workflows)
3. `~/.env` file (persistent default, supports both `export KEY=val` and `KEY=val`)

This means direnv users get automatic per-directory config, CI can inject env vars, and casual users just drop a line in `~/.env`.

### Thin API wrapper

`TogglAPI` is a minimal HTTP client, not a domain model. Methods map directly to Toggl REST endpoints. No caching, no ORM-style objects, no state beyond the auth header. This keeps the code easy to extend when new endpoints are needed.

### Single workspace assumption

Most individual users have one workspace. tgl uses the first workspace returned by the API rather than requiring workspace configuration. If multi-workspace support becomes necessary, it should be opt-in (e.g., `--workspace` flag) without burdening single-workspace users.

### Presets over memory

Starting a timer shouldn't require remembering project IDs or exact tag names. Presets in `~/.config/tgl/config.toml` map short names to project/tag combos:

```toml
[presets.website]
project_id = 12345678
project_name = "Website redesign"
tags = ["Development"]

[presets.admin]
project_id = 87654321
project_name = "Admin"
tags = ["Meetings"]
```

`tgl init` generates this file from your Toggl workspace — one preset per active project. Edit it to add tags, remove projects you don't use, or rename keys.

Usage:

```
tgl start -P website "fix landing page"  # use a preset
tgl start                                # interactive: pick preset, enter description
```

The interactive flow is intentionally minimal: pick a number, type a description, done. No menus-within-menus.

### Toggl organization model

tgl assumes a specific Toggl hierarchy:

- **Clients** are areas of responsibility (e.g., Research, Engineering, Admin)
- **Projects** are specific efforts within an area
- **Tags** classify the type of work (e.g., Development, Meetings, Planning)

This maps to: *what area*, *what project*, *what kind of work*.

## Architecture

```
tgl/
  cli.py      Click commands. Parses args, calls API, prints output.
  api.py      TogglAPI class. HTTP methods + token loading. No CLI concerns.
  config.py   Preset loading from ~/.config/tgl/config.toml.
tests/
  test_cli.py     Tests against mocked API. No network calls.
  test_config.py  Tests for config loading and preset resolution.
```

The boundary is clean: `cli.py` never constructs URLs or headers; `api.py` never prints or parses arguments; `config.py` handles file I/O for presets but knows nothing about the API or CLI.

## Development

Tests are written first. All CLI and config tests use mocks — no network calls. Run `uv run pytest` before every commit.

## Future direction

Features worth considering:

- `tgl ls` to list recent entries
- Shell completions for preset names
- Duration display in `start` output (elapsed since start)

Features intentionally out of scope:

- Reporting and analytics
- Project/workspace/client management
- Offline mode or local caching
