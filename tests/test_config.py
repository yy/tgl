"""Tests for tgl config and presets."""

import textwrap

from tgl.config import get_presets, load_config


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("tgl.config.CONFIG_FILE", tmp_path / "nonexistent.toml")
    assert load_config() == {}


def test_load_config_valid(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        textwrap.dedent("""\
        [presets.research]
        project_id = 123
        project_name = "Research"
        tags = ["Core activities"]
    """)
    )
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)
    config = load_config()
    assert config["presets"]["research"]["project_id"] == 123
    assert config["presets"]["research"]["tags"] == ["Core activities"]


def test_get_presets_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("tgl.config.CONFIG_FILE", tmp_path / "nonexistent.toml")
    assert get_presets() == {}


def test_get_presets_multiple(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        textwrap.dedent("""\
        [presets.research]
        project_id = 100
        project_name = "Research"
        tags = ["Core activities"]

        [presets.admin]
        project_id = 200
        project_name = "Admin"
        tags = ["Admin"]
    """)
    )
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)
    presets = get_presets()
    assert len(presets) == 2
    assert presets["research"]["project_id"] == 100
    assert presets["admin"]["project_id"] == 200


def test_get_presets_no_tags(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        textwrap.dedent("""\
        [presets.quick]
        project_id = 300
        project_name = "Quick task"
    """)
    )
    monkeypatch.setattr("tgl.config.CONFIG_FILE", config_file)
    presets = get_presets()
    assert presets["quick"]["project_id"] == 300
    assert "tags" not in presets["quick"]
