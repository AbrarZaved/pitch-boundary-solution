import json

import pytest

from pipeline.config import AppConfig


def valid_config() -> dict:
    return {
        "video_path": "x.mp4",
        "generate_synthetic_input": False,
        "target_fps": 30,
        "confidence_threshold": 0.5,
        "field_detector": {
            "type": "mask_threshold_v1",
            "sport": "football",
            "min_area": 1000,
        },
        "crop_search": {"aspect_ratio": "16:9", "padding_px": 20},
        "reporting": {
            "base_url": "http://localhost:5000",
            "progress_interval_frames": 10,
            "timeout_seconds": 1,
            "max_retries": 0,
            "retry_backoff_seconds": 0,
        },
        "sample_count": 10,
        "frame_stride": 1,
        "max_frames": None,
        "max_consecutive_detector_errors": 3,
        "debug_mode": False,
    }


def write_config(tmp_path, data: dict):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_valid_config(tmp_path):
    config = AppConfig.load(str(write_config(tmp_path, valid_config())))
    assert config.video_path == "x.mp4"
    assert config.sample_count == 10


def test_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        AppConfig.load(str(tmp_path / "missing.json"))
    assert exc.value.code == 2


def test_invalid_json_exits(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        AppConfig.load(str(path))
    assert exc.value.code == 2


def test_invalid_value_exits(tmp_path):
    data = valid_config()
    data["confidence_threshold"] = 5
    with pytest.raises(SystemExit):
        AppConfig.load(str(write_config(tmp_path, data)))


def test_unknown_top_level_key_exits(tmp_path):
    data = valid_config()
    data["unexpected"] = 123
    with pytest.raises(SystemExit):
        AppConfig.load(str(write_config(tmp_path, data)))


def test_unknown_nested_key_exits(tmp_path):
    data = valid_config()
    data["field_detector"]["typo"] = True
    with pytest.raises(SystemExit):
        AppConfig.load(str(write_config(tmp_path, data)))


def test_conflicting_sampling_modes_exit(tmp_path):
    data = valid_config()
    data["sample_count"] = 10
    data["max_frames"] = 10
    with pytest.raises(SystemExit):
        AppConfig.load(str(write_config(tmp_path, data)))