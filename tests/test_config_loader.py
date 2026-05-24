from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pi_face_greeter.config_loader import DEFAULT_CONFIG_PATH, PROJECT_ROOT, load_config


def test_project_root_is_repo_root() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "config" / "config.yaml").is_file()


def test_load_default_config() -> None:
    config = load_config()
    assert config["app"]["name"] == "Pi Face Greeter"
    assert config["pir"]["enabled"] is False
    assert config["pir"]["gpio_pin"] == 17
    assert config["camera"]["backend"] == "picamera2"


def test_load_config_resolves_relative_paths(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump(
            {
                "camera": {"capture_dir": "data/captured"},
                "logging": {"file": "data/logs/test.log"},
            }
        ),
        encoding="utf-8",
    )

    original_root = PROJECT_ROOT
    import pi_face_greeter.config_loader as config_module

    config_module.PROJECT_ROOT = tmp_path
    try:
        config = load_config(config_file)
        assert config["camera"]["capture_dir"] == str(tmp_path / "data" / "captured")
        assert config["logging"]["file"] == str(tmp_path / "data" / "logs" / "test.log")
    finally:
        config_module.PROJECT_ROOT = original_root


def test_load_config_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_default_config_path_exists() -> None:
    assert DEFAULT_CONFIG_PATH.is_file()
