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

## Development

```
uv sync --group dev
uv run pytest
```

## Design

See [docs/design.md](docs/design.md) for design principles and architectural decisions.
