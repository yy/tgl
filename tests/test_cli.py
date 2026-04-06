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
    api.start_timer.assert_called_once_with(
        "test task", 123, project_id=None, tags=None, start_time=None
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


@patch("tgl.cli.get_presets")
@patch("tgl.cli.TogglAPI")
def test_start_with_preset(mock_api_cls, mock_presets):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.start_timer.return_value = {"id": 789}
    mock_presets.return_value = {
        "research": {
            "project_id": 100,
            "project_name": "Research-related",
            "tags": ["Core activities"],
        }
    }

    runner = CliRunner()
    result = runner.invoke(
        main, ["--apitoken", "fake", "start", "-P", "research", "writing paper"]
    )

    assert result.exit_code == 0
    assert "Started: writing paper" in result.output
    assert "Research-related" in result.output
    api.start_timer.assert_called_once_with(
        "writing paper",
        123,
        project_id=100,
        tags=["Core activities"],
        start_time=None,
    )


@patch("tgl.cli.get_presets")
@patch("tgl.cli.TogglAPI")
def test_start_with_unknown_preset(mock_api_cls, mock_presets):
    api = MagicMock()
    mock_api_cls.return_value = api
    mock_presets.return_value = {"research": {"project_id": 100}}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "start", "-P", "bogus", "task"])

    assert result.exit_code != 0
    assert "bogus" in result.output
    assert "research" in result.output


@patch("tgl.cli.get_presets")
@patch("tgl.cli.TogglAPI")
def test_start_interactive_pick_preset(mock_api_cls, mock_presets):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.start_timer.return_value = {"id": 999}
    mock_presets.return_value = {
        "research": {
            "project_id": 100,
            "project_name": "Research-related",
            "tags": ["Core activities"],
        },
        "admin": {
            "project_id": 200,
            "project_name": "Admin tasks",
            "tags": ["Admin"],
        },
    }

    runner = CliRunner()
    # Input: pick preset 1, then enter description
    result = runner.invoke(
        main, ["--apitoken", "fake", "start"], input="1\nreviewing paper\n"
    )

    assert result.exit_code == 0
    assert "Started: reviewing paper" in result.output


@patch("tgl.cli.get_presets")
@patch("tgl.cli.TogglAPI")
def test_start_interactive_no_presets_falls_back(mock_api_cls, mock_presets):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.start_timer.return_value = {"id": 999}
    mock_presets.return_value = {}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "start"], input="just a task\n")

    assert result.exit_code == 0
    assert "Started: just a task" in result.output


@patch("tgl.cli.TogglAPI")
def test_resume_last_timer(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.current_timer.return_value = None
    api.recent_entries.return_value = [
        {
            "description": "writing paper",
            "project_id": 100,
            "tags": ["Core activities"],
            "workspace_id": 123,
        }
    ]
    api.start_timer.return_value = {"id": 555}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "resume"])

    assert result.exit_code == 0
    assert "Resumed: writing paper" in result.output
    api.start_timer.assert_called_once_with(
        "writing paper", 123, project_id=100, tags=["Core activities"]
    )


@patch("tgl.cli.TogglAPI")
def test_resume_no_recent_entries(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.current_timer.return_value = None
    api.recent_entries.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "resume"])

    assert result.exit_code == 0
    assert "No recent entries" in result.output


@patch("tgl.cli.TogglAPI")
def test_resume_while_timer_running(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.current_timer.return_value = {"description": "already running", "duration": -1}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "resume"])

    assert result.exit_code == 0
    assert "already running" in result.output


@patch("tgl.cli.TogglAPI")
def test_resume_skips_entries_without_description(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.current_timer.return_value = None
    api.recent_entries.return_value = [
        {"description": "", "project_id": None, "tags": [], "workspace_id": 123},
        {
            "description": "real task",
            "project_id": 50,
            "tags": ["Admin"],
            "workspace_id": 123,
        },
    ]
    api.start_timer.return_value = {"id": 600}

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "resume"])

    assert result.exit_code == 0
    assert "Resumed: real task" in result.output
    api.start_timer.assert_called_once_with(
        "real task", 123, project_id=50, tags=["Admin"]
    )


def _mock_init_api(mock_api_cls):
    """Set up a mock API with clients, projects, and tags for init tests."""
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.get_clients.return_value = [
        {"id": 10, "name": "Research"},
        {"id": 20, "name": "Teaching"},
        {"id": 30, "name": "Service"},
    ]
    api.get_projects.return_value = [
        {"id": 100, "name": "Paper writing", "active": True, "client_id": 10},
        {"id": 101, "name": "Grant proposal", "active": True, "client_id": 10},
        {"id": 200, "name": "Course prep", "active": True, "client_id": 20},
        {"id": 300, "name": "Committee work", "active": True, "client_id": 30},
        {"id": 999, "name": "Old project", "active": False, "client_id": 10},
    ]
    api.get_tags.return_value = [
        {"id": 1, "name": "Deep work"},
        {"id": 2, "name": "Admin"},
        {"id": 3, "name": "Meetings"},
    ]
    return api


@patch("tgl.cli.TogglAPI")
def test_init_all_areas_all_projects(mock_api_cls, tmp_path, monkeypatch):
    _mock_init_api(mock_api_cls)
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("tgl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)

    runner = CliRunner()
    # all areas, all projects, skip tags for each (4 active projects)
    result = runner.invoke(
        main, ["--apitoken", "fake", "init"], input="all\nall\n\n\n\n\n"
    )

    assert result.exit_code == 0, result.output
    assert config_file.exists()
    content = config_file.read_text()
    assert "paper-writing" in content
    assert "grant-proposal" in content
    assert "course-prep" in content
    assert "committee-work" in content


@patch("tgl.cli.TogglAPI")
def test_init_select_specific_areas(mock_api_cls, tmp_path, monkeypatch):
    _mock_init_api(mock_api_cls)
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("tgl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)

    runner = CliRunner()
    # Pick area 1 (Research) only, all projects in it, skip tags
    result = runner.invoke(main, ["--apitoken", "fake", "init"], input="1\nall\n\n\n")

    assert result.exit_code == 0, result.output
    content = config_file.read_text()
    assert "paper-writing" in content
    assert "grant-proposal" in content
    assert "course-prep" not in content
    assert "committee-work" not in content


@patch("tgl.cli.TogglAPI")
def test_init_select_specific_projects(mock_api_cls, tmp_path, monkeypatch):
    _mock_init_api(mock_api_cls)
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("tgl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)

    runner = CliRunner()
    # All areas, pick only project 1 and 3, skip tags
    result = runner.invoke(main, ["--apitoken", "fake", "init"], input="all\n1,3\n\n\n")

    assert result.exit_code == 0, result.output
    import tomllib

    with open(config_file, "rb") as f:
        config = tomllib.load(f)
    keys = list(config["presets"].keys())
    assert len(keys) == 2


@patch("tgl.cli.TogglAPI")
def test_init_assign_tags(mock_api_cls, tmp_path, monkeypatch):
    _mock_init_api(mock_api_cls)
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("tgl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)

    runner = CliRunner()
    # Area 1 (Research), all projects (Grant proposal, Paper writing sorted),
    # Tags sorted: 1=Admin, 2=Deep work, 3=Meetings
    # Grant proposal gets tag 2 (Deep work), Paper writing gets tag 1,3 (Admin, Meetings)
    result = runner.invoke(
        main, ["--apitoken", "fake", "init"], input="1\nall\n2\n1,3\n"
    )

    assert result.exit_code == 0, result.output
    import tomllib

    with open(config_file, "rb") as f:
        config = tomllib.load(f)
    assert config["presets"]["grant-proposal"]["tags"] == ["Deep work"]
    assert config["presets"]["paper-writing"]["tags"] == ["Admin", "Meetings"]


@patch("tgl.cli.TogglAPI")
def test_init_shows_summary(mock_api_cls, tmp_path, monkeypatch):
    _mock_init_api(mock_api_cls)
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("tgl.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "init"], input="1\nall\n1\n\n")

    assert result.exit_code == 0, result.output
    # Should show a summary before writing
    assert "Summary" in result.output or "summary" in result.output
    assert "Grant proposal" in result.output
    assert "Paper writing" in result.output


def test_date_range_today():
    from tgl.cli import _date_range
    import datetime

    ref = datetime.date(2026, 3, 16)  # a Monday
    start, end = _date_range("today", ref)
    assert start == datetime.date(2026, 3, 16)
    assert end == datetime.date(2026, 3, 16)


def test_date_range_week():
    from tgl.cli import _date_range
    import datetime

    ref = datetime.date(2026, 3, 18)  # a Wednesday
    start, end = _date_range("week", ref)
    assert start == datetime.date(2026, 3, 16)  # Monday
    assert end == datetime.date(2026, 3, 18)


def test_date_range_last_week():
    from tgl.cli import _date_range
    import datetime

    ref = datetime.date(2026, 3, 18)  # a Wednesday
    start, end = _date_range("last-week", ref)
    assert start == datetime.date(2026, 3, 9)  # prev Monday
    assert end == datetime.date(2026, 3, 15)  # prev Sunday


def test_date_range_month():
    from tgl.cli import _date_range
    import datetime

    ref = datetime.date(2026, 3, 18)
    start, end = _date_range("month", ref)
    assert start == datetime.date(2026, 3, 1)
    assert end == datetime.date(2026, 3, 18)


@patch("tgl.cli.TogglAPI")
def test_summary_today(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.get_projects.return_value = [
        {"id": 100, "name": "Research", "active": True},
        {"id": 200, "name": "Admin", "active": True},
    ]
    api.time_entries_between.return_value = [
        {
            "description": "writing",
            "project_id": 100,
            "duration": 3600,
            "tags": ["Core activities"],
        },
        {
            "description": "emails",
            "project_id": 200,
            "duration": 1800,
            "tags": ["Admin"],
        },
        {
            "description": "reading",
            "project_id": 100,
            "duration": 900,
            "tags": ["Core activities"],
        },
    ]

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "summary"])

    assert result.exit_code == 0
    assert "Research" in result.output
    assert "Admin" in result.output
    assert "1:15:00" in result.output  # 3600 + 900 = 4500s = 1:15:00
    assert "0:30:00" in result.output  # 1800s
    assert "1:45:00" in result.output  # total


@patch("tgl.cli.TogglAPI")
def test_summary_no_entries(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.get_projects.return_value = []
    api.time_entries_between.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "summary"])

    assert result.exit_code == 0
    assert "No entries" in result.output


@patch("tgl.cli.TogglAPI")
def test_summary_with_period(mock_api_cls):
    api = MagicMock()
    mock_api_cls.return_value = api
    api.get_workspace_id.return_value = 123
    api.get_projects.return_value = [
        {"id": 100, "name": "Research", "active": True},
    ]
    api.time_entries_between.return_value = [
        {"description": "writing", "project_id": 100, "duration": 7200, "tags": []},
    ]

    runner = CliRunner()
    result = runner.invoke(main, ["--apitoken", "fake", "summary", "week"])

    assert result.exit_code == 0
    assert "Research" in result.output
    assert "2:00:00" in result.output
