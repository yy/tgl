# tgl

A command-line interface for [Toggl Track](https://toggl.com/track/) timers. Start, stop, and check timers without leaving the terminal.

## Install

Requires Python 3.13+.

```
uv tool install tgl
```

Or run without installing:

```
uvx tgl start "writing docs"
```

## Setup

Get your API token from [toggl.com/profile](https://track.toggl.com/profile) (scroll to "API Token"), then add it to `~/.env`:

```
TOGGL_API_TOKEN=your_token_here
```

Both `export TOGGL_API_TOKEN=...` and bare `KEY=value` formats work. The token is resolved in order: `--apitoken` flag, `TOGGL_API_TOKEN` env var, `~/.env` file.

## Usage

```
tgl start "writing docs"          # start a timer
tgl status                        # check what's running
tgl stop                          # stop the current timer
tgl resume                        # restart the last timer
tgl summary                       # today's time by project
tgl summary week                  # this week so far
tgl summary last-week             # previous Mon-Sun
tgl summary month                 # this month so far
tgl report total                  # last week's filtered total (Sun-Sat)
tgl report batch weekly_sheet     # named multi-line report from reports.toml
```

### Presets

Generate a config file from your Toggl workspace:

```
tgl init
```

This walks you through picking which projects to include and assigning default tags. The result is saved to `~/.config/tgl/config.toml`:

```toml
[presets.website]
project_id = 12345678
project_name = "Website redesign"
tags = ["Development"]
```

Then start timers with presets:

```
tgl start -P website "fix landing page"
```

Or run `tgl start` with no arguments for interactive mode — pick a preset from a numbered list, type a description, done.

### Options

```
tgl start "deep work" -p 12345              # assign to project (by ID)
tgl start "review" -t bug -t urgent         # add tags
tgl start -P admin "emails"                 # use a preset
tgl start                                   # interactive mode
tgl --apitoken TOKEN start "one-off"        # override token
```

### Reporting

`tgl summary` remains the project-by-project overview. Use `tgl report` for
filter-oriented totals and batch reports built on the Toggl Reports API:

```
tgl report total --range 2026-03-01:2026-03-07 --client 123456
tgl report total this-week --tag 789012
tgl report batch weekly_sheet --copy
tgl report import --name weekly_sheet /path/to/entries.json
```

Report sets live in `~/.config/tgl/reports.toml`:

```toml
[report_sets.weekly_sheet]

[[report_sets.weekly_sheet.entries]]
label = "Client Work"
clients = [123456, 234567]

[[report_sets.weekly_sheet.entries]]
label = "Internal"
tags = [789012]
```

## Development

```
uv sync --group dev
uv run pytest
```

## Design

See [docs/design.md](docs/design.md) for design principles and architectural decisions.
