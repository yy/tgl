"""CLI tests for reporting commands."""

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tgl.cli import main

REPORT_SET_NAME = "default_set"
CLIENT_IDS = [101, 202]
TAG_IDS = [303]
WORKSPACE_ID = 4040


def _write_report_file(path: Path):
    path.write_text(
        f"""
[report_sets.{REPORT_SET_NAME}]

[[report_sets.{REPORT_SET_NAME}.entries]]
label = "Client Work"
clients = [{CLIENT_IDS[0]}, {CLIENT_IDS[1]}]

[[report_sets.{REPORT_SET_NAME}.entries]]
label = "Tagged Work"
tags = [{TAG_IDS[0]}]

[[report_sets.{REPORT_SET_NAME}.entries]]
label = "Unfiltered"
""".lstrip()
    )


@patch("tgl.cli.TogglAPI")
def test_report_total_with_clients(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.return_value = "User,Project,Duration\nAlice,Work,04:15:00\n"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "total",
            "--range",
            "2026-03-01:2026-03-07",
            "--client",
            str(CLIENT_IDS[0]),
        ],
    )

    assert result.exit_code == 0
    assert result.output == "04:15:00\n"
    api.summary_report_csv.assert_called_once_with(
        WORKSPACE_ID,
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 7),
        client_ids=[CLIENT_IDS[0]],
        tag_ids=None,
    )


@patch("tgl.cli.TogglAPI")
def test_report_total_with_tags(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.return_value = "User,Project,Duration\nAlice,Work,00:45:00\n"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "total",
            "--range",
            "2026-03-01:2026-03-07",
            "--tag",
            str(TAG_IDS[0]),
        ],
    )

    assert result.exit_code == 0
    assert result.output == "00:45:00\n"
    api.summary_report_csv.assert_called_once()


@patch("tgl.cli.TogglAPI")
def test_report_total_with_clients_and_tags(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.return_value = "User,Project,Duration\nAlice,Work,00:30:00\n"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "total",
            "--range",
            "2026-03-01:2026-03-07",
            "--client",
            str(CLIENT_IDS[0]),
            "--tag",
            str(TAG_IDS[0]),
        ],
    )

    assert result.exit_code == 0
    assert result.output == "00:30:00\n"
    api.summary_report_csv.assert_called_once()
    args, kwargs = api.summary_report_csv.call_args
    assert args[0] == WORKSPACE_ID
    assert kwargs["client_ids"] == [CLIENT_IDS[0]]
    assert kwargs["tag_ids"] == [TAG_IDS[0]]


@patch("tgl.cli.TogglAPI")
def test_report_total_empty_results_prints_zero(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.return_value = "User,Project,Duration\n"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "total",
            "--range",
            "2026-03-01:2026-03-07",
        ],
    )

    assert result.exit_code == 0
    assert result.output == "00:00:00\n"


@patch("tgl.cli.TogglAPI")
def test_report_batch_reads_named_set_and_preserves_order(mock_api_cls, tmp_path):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.side_effect = [
        "User,Project,Duration\nAlice,Work,01:00:00\n",
        "User,Project,Duration\nAlice,Work,00:30:00\n",
        "User,Project,Duration\nAlice,Work,02:00:00\n",
    ]
    report_file = tmp_path / "reports.toml"
    _write_report_file(report_file)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "batch",
            REPORT_SET_NAME,
            "--range",
            "2026-03-01:2026-03-07",
            "--file",
            str(report_file),
        ],
    )

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "Client Work, 01:00:00",
        "Tagged Work, 00:30:00",
        "Unfiltered, 02:00:00",
    ]


@patch("tgl.cli.subprocess.run")
@patch("tgl.cli.TogglAPI")
def test_report_batch_copy_uses_tsv_payload(mock_api_cls, mock_run, tmp_path):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    api.summary_report_csv.side_effect = [
        "User,Project,Duration\nAlice,Work,01:00:00\n",
        "User,Project,Duration\nAlice,Work,00:30:00\n",
        "User,Project,Duration\nAlice,Work,02:00:00\n",
    ]
    report_file = tmp_path / "reports.toml"
    _write_report_file(report_file)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "batch",
            REPORT_SET_NAME,
            "--range",
            "2026-03-01:2026-03-07",
            "--file",
            str(report_file),
            "--copy",
        ],
    )

    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["pbcopy"],
        input="01:00:00\t00:30:00\t02:00:00",
        text=True,
        check=True,
    )


@patch("tgl.cli.TogglAPI")
def test_report_batch_missing_set_fails_clearly(mock_api_cls, tmp_path):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = WORKSPACE_ID
    report_file = tmp_path / "reports.toml"
    _write_report_file(report_file)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "batch",
            "missing",
            "--file",
            str(report_file),
        ],
    )

    assert result.exit_code != 0
    assert "missing" in result.output
    assert REPORT_SET_NAME in result.output


@patch("tgl.cli.TogglAPI")
def test_report_batch_invalid_toml_fails_clearly(mock_api_cls, tmp_path):
    mock_api_cls.return_value = MagicMock()
    report_file = tmp_path / "reports.toml"
    report_file.write_text("[report_sets.invalid name]\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "batch",
            REPORT_SET_NAME,
            "--file",
            str(report_file),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid report file" in result.output
    assert str(report_file) in result.output


@patch("tgl.cli.TogglAPI")
def test_report_import_writes_report_set(mock_api_cls, tmp_path):
    mock_api_cls.return_value = MagicMock()
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
    report_file = tmp_path / "reports.toml"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "import",
            "--name",
            REPORT_SET_NAME,
            str(legacy_file),
            "--file",
            str(report_file),
        ],
    )

    assert result.exit_code == 0
    assert report_file.exists()
    assert REPORT_SET_NAME in report_file.read_text()
    assert 'label = "Client Work"' in report_file.read_text()
    assert f"clients = [{CLIENT_IDS[0]}, {CLIENT_IDS[1]}]" in report_file.read_text()
    assert f"tags = [{TAG_IDS[0]}]" in report_file.read_text()


@patch("tgl.cli.TogglAPI")
def test_report_import_invalid_json_fails_clearly(mock_api_cls, tmp_path):
    mock_api_cls.return_value = MagicMock()
    legacy_file = tmp_path / "entries.json"
    legacy_file.write_text("{not json")
    report_file = tmp_path / "reports.toml"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--apitoken",
            "fake",
            "report",
            "import",
            "--name",
            REPORT_SET_NAME,
            str(legacy_file),
            "--file",
            str(report_file),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid legacy report file" in result.output
    assert str(legacy_file) in result.output
