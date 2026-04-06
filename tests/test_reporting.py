"""Tests for reporting helpers."""

import datetime
import json

import pytest

from tgl.reporting import (
    format_report_duration,
    import_legacy_report_set,
    load_report_sets,
    parse_report_date_range,
    parse_report_period,
    total_seconds_from_csv,
    write_report_sets,
)

REPORT_SET_NAME = "default_set"
CLIENT_IDS = [101, 202]
TAG_IDS = [303]
WORKSPACE_ID = 4040


def test_parse_report_period_today():
    ref = datetime.date(2026, 3, 18)

    start, end = parse_report_period("today", ref)

    assert start == datetime.date(2026, 3, 18)
    assert end == datetime.date(2026, 3, 18)


def test_parse_report_period_this_week():
    ref = datetime.date(2026, 3, 18)  # Wednesday

    start, end = parse_report_period("this-week", ref)

    assert start == datetime.date(2026, 3, 15)  # Sunday
    assert end == datetime.date(2026, 3, 18)


def test_parse_report_period_last_week():
    ref = datetime.date(2026, 3, 18)  # Wednesday

    start, end = parse_report_period("last-week", ref)

    assert start == datetime.date(2026, 3, 8)
    assert end == datetime.date(2026, 3, 14)


def test_parse_report_period_month():
    ref = datetime.date(2026, 3, 18)

    start, end = parse_report_period("month", ref)

    assert start == datetime.date(2026, 3, 1)
    assert end == datetime.date(2026, 3, 18)


def test_parse_report_date_range_valid():
    start, end = parse_report_date_range("2026-03-01:2026-03-07")

    assert start == datetime.date(2026, 3, 1)
    assert end == datetime.date(2026, 3, 7)


def test_parse_report_date_range_invalid_format():
    with pytest.raises(ValueError, match="START:END"):
        parse_report_date_range("2026-03-01")


def test_parse_report_date_range_rejects_reverse_order():
    with pytest.raises(ValueError, match="must not be after"):
        parse_report_date_range("2026-03-07:2026-03-01")


def test_total_seconds_from_csv_multiple_rows():
    csv_text = "User,Project,Duration\nAlice,Work,01:30:00\nBob,Work,02:45:30\n"

    assert total_seconds_from_csv(csv_text) == 15330
    assert format_report_duration(15330) == "04:15:30"


def test_total_seconds_from_csv_header_only():
    csv_text = "User,Project,Duration\n"

    assert total_seconds_from_csv(csv_text) == 0
    assert format_report_duration(0) == "00:00:00"


def test_total_seconds_from_csv_handles_bom_prefixed_text():
    csv_text = "\ufeffUser,Project,Duration\nAlice,Work,00:45:00\n"

    assert total_seconds_from_csv(csv_text) == 2700


def test_total_seconds_from_csv_requires_duration_column():
    csv_text = "User,Project\nAlice,Work\n"

    with pytest.raises(ValueError, match="Duration"):
        total_seconds_from_csv(csv_text)


def test_total_seconds_from_csv_rejects_malformed_duration():
    csv_text = "User,Project,Duration\nAlice,Work,1 hour\n"

    with pytest.raises(ValueError, match="Invalid duration"):
        total_seconds_from_csv(csv_text)


def test_load_report_sets_missing_file_returns_empty(tmp_path):
    assert load_report_sets(tmp_path / "missing.toml") == {}


def test_load_report_sets_reads_entries(tmp_path):
    report_file = tmp_path / "reports.toml"
    report_file.write_text(
        f"""
[report_sets.{REPORT_SET_NAME}]

[[report_sets.{REPORT_SET_NAME}.entries]]
label = "Client Work"
clients = [{CLIENT_IDS[0]}, {CLIENT_IDS[1]}]

[[report_sets.{REPORT_SET_NAME}.entries]]
label = "Tagged Work"
tags = [{TAG_IDS[0]}]
""".lstrip()
    )

    report_sets = load_report_sets(report_file)

    assert list(report_sets.keys()) == [REPORT_SET_NAME]
    assert report_sets[REPORT_SET_NAME]["entries"][0]["label"] == "Client Work"
    assert report_sets[REPORT_SET_NAME]["entries"][1]["tags"] == TAG_IDS


def test_import_legacy_report_set_maps_entries_json(tmp_path):
    legacy_file = tmp_path / "entries.json"
    legacy_file.write_text(
        json.dumps(
            [
                {
                    "title": "Client Work",
                    "params": {
                        "workspace_id": WORKSPACE_ID,
                        "client_ids": CLIENT_IDS,
                    },
                },
                {
                    "title": "Tagged Work",
                    "params": {
                        "workspace_id": WORKSPACE_ID,
                        "tag_ids": TAG_IDS,
                    },
                },
            ]
        )
    )

    report_set = import_legacy_report_set(legacy_file)

    assert report_set == {
        "entries": [
            {"label": "Client Work", "clients": CLIENT_IDS},
            {"label": "Tagged Work", "tags": TAG_IDS},
        ]
    }


def test_import_legacy_report_set_rejects_multiple_workspaces(tmp_path):
    legacy_file = tmp_path / "entries.json"
    legacy_file.write_text(
        json.dumps(
            [
                {
                    "title": "Client Work",
                    "params": {"workspace_id": 1, "client_ids": [10]},
                },
                {
                    "title": "Tagged Work",
                    "params": {"workspace_id": 2, "tag_ids": [20]},
                },
            ]
        )
    )

    with pytest.raises(ValueError, match="single workspace"):
        import_legacy_report_set(legacy_file)


def test_write_report_sets_round_trip(tmp_path):
    report_file = tmp_path / "reports.toml"
    report_sets = {
        REPORT_SET_NAME: {
            "entries": [
                {"label": "Client Work", "clients": CLIENT_IDS},
                {"label": "Tagged Work", "tags": TAG_IDS},
                {"label": "Unfiltered"},
            ]
        }
    }

    write_report_sets(report_file, report_sets)

    loaded = load_report_sets(report_file)
    assert loaded == report_sets


def test_write_report_sets_round_trip_with_special_set_name(tmp_path):
    report_file = tmp_path / "reports.toml"
    special_name = "team.alpha 1"
    report_sets = {
        special_name: {
            "entries": [
                {"label": "Client Work", "clients": CLIENT_IDS},
            ]
        }
    }

    write_report_sets(report_file, report_sets)

    loaded = load_report_sets(report_file)
    assert loaded == report_sets
