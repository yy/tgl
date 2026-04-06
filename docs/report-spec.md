# Reporting in `tgl`

## Summary

`tgl summary` stays as the existing project breakdown command.

Reporting that needs client/tag filters or spreadsheet-oriented output lives under a
new `tgl report` namespace built on the Toggl Reports API v3.

The design goal is to keep reporting composable:

- `tgl report total` is the atomic primitive
- `tgl report batch` assembles a named multi-line report from config
- `tgl report import` migrates legacy `entries.json` files into the new config
  format

## Commands

### `tgl report total`

Print a bare `HH:MM:SS` total for a date range and optional filters.

```sh
tgl report total
tgl report total this-week
tgl report total --range 2026-03-01:2026-03-07 --client 123456
tgl report total --range 2026-03-01:2026-03-07 --tag 789012
tgl report total --range 2026-03-01:2026-03-07 --client 123456 --tag 789012
```

Notes:

- Default period is `last-week`
- Report-week semantics are Sunday-based
- `--range START:END` overrides the named period
- Repeating `--client` or `--tag` adds multiple IDs to the filter

### `tgl report batch`

Run a named report set from `~/.config/tgl/reports.toml`.

```sh
tgl report batch weekly_sheet
tgl report batch weekly_sheet --copy
tgl report batch weekly_sheet --range 2026-03-01:2026-03-07
tgl report batch weekly_sheet --file /tmp/reports.toml
```

Output format:

```text
Client Work, 61:48:51
Internal, 17:27:10
Unfiltered, 02:55:17
```

With `--copy`, `tgl` copies the tab-separated durations to the macOS clipboard via
`pbcopy`, which preserves the old spreadsheet paste workflow without making clipboard
behavior the default.

### `tgl report import`

Import a legacy `entries.json` file into `reports.toml`.

```sh
tgl report import --name weekly_sheet /path/to/entries.json
```

This creates or updates a named report set in `~/.config/tgl/reports.toml`.

## Config format

Reports live separately from timer presets:

- Presets: `~/.config/tgl/config.toml`
- Reports: `~/.config/tgl/reports.toml`

Example:

```toml
[report_sets.weekly_sheet]

[[report_sets.weekly_sheet.entries]]
label = "Client Work"
clients = [123456, 234567]

[[report_sets.weekly_sheet.entries]]
label = "Internal"
tags = [789012]

[[report_sets.weekly_sheet.entries]]
label = "Unfiltered"
```

Rules:

- `clients` and `tags` are both optional
- If both are present, Toggl applies its normal AND semantics
- If both are absent, the entry means an unfiltered workspace total
- Entry order is preserved in `tgl report batch` output

## API

Filtered reporting uses the Toggl Reports API v3:

```text
POST https://api.track.toggl.com/reports/api/v3/workspace/{wid}/summary/time_entries.csv
```

Request body:

```json
{
  "start_date": "2026-03-01",
  "end_date": "2026-03-07",
  "client_ids": [123456],
  "tag_ids": [789012]
}
```

The response is CSV. `tgl` decodes BOM-prefixed responses and sums the `Duration`
column with the stdlib `csv` module.

## Notes

- `tgl` still assumes a single workspace and resolves it once from the API
- `tgl summary` keeps its current Monday-based project summary behavior
- The old `urls.txt` format is not a runtime interface in `tgl`
