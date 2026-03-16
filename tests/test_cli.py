"""Tests for tgl CLI."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tgl.cli import main


@patch("tgl.cli.TogglAPI")
def test_start(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.start_timer.return_value = {"id": 456}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "start", "test task"])

    assert result.exit_code == 0
    assert "Started: test task" in result.output
    assert "456" in result.output
    api.start_timer.assert_called_once_with(
        "test task", 123, project_id=None, tags=None
    )


@patch("tgl.cli.TogglAPI")
def test_stop_running(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.stop_timer.return_value = {"description": "test task", "duration": 3661}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "stop"])

    assert result.exit_code == 0
    assert "Stopped: test task" in result.output
    assert "1:01:01" in result.output


@patch("tgl.cli.TogglAPI")
def test_stop_no_timer(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.stop_timer.return_value = None

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "stop"])

    assert result.exit_code == 0
    assert "No timer running" in result.output


@patch("tgl.cli.TogglAPI")
def test_status_running(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.current_timer.return_value = {
        "description": "coding",
        "start": "2025-01-01T10:00:00+00:00",
    }

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "status"])

    assert result.exit_code == 0
    assert "Running: coding" in result.output


@patch("tgl.cli.TogglAPI")
def test_status_no_timer(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.current_timer.return_value = None

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "status"])

    assert result.exit_code == 0
    assert "No timer running" in result.output
