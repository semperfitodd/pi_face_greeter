from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    _resolve_paths(config)
    return config


def _resolve_paths(config: dict[str, Any]) -> None:
    camera = config.get("camera", {})
    if capture_dir := camera.get("capture_dir"):
        camera["capture_dir"] = str(_resolve_project_path(capture_dir))

    logging_cfg = config.get("logging", {})
    if log_file := logging_cfg.get("file"):
        logging_cfg["file"] = str(_resolve_project_path(log_file))

    enrollment_cfg = config.get("enrollment", {})
    if known_faces_dir := enrollment_cfg.get("known_faces_dir"):
        enrollment_cfg["known_faces_dir"] = str(_resolve_project_path(known_faces_dir))

    diagnostics_cfg = config.get("diagnostics", {})
    if snapshot_dir := diagnostics_cfg.get("snapshot_dir"):
        diagnostics_cfg["snapshot_dir"] = str(_resolve_project_path(snapshot_dir))

    tts_cfg = config.get("tts", {})
    piper_cfg = tts_cfg.get("piper", {})
    if model_path := piper_cfg.get("model"):
        piper_cfg["model"] = str(_resolve_project_path(model_path))

    stt_cfg = config.get("stt", {})
    if stt_model := stt_cfg.get("model"):
        stt_cfg["model"] = str(_resolve_project_path(stt_model))
    if vad_model := stt_cfg.get("vad_model"):
        stt_cfg["vad_model"] = str(_resolve_project_path(vad_model))

    wake_cfg = config.get("wake_word", {})
    if wake_model := wake_cfg.get("model"):
        if str(wake_model).endswith(".onnx"):
            wake_cfg["model"] = str(_resolve_project_path(wake_model))


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path
