import json

import pytest

from pipeline.config import AppConfig


def test_load_valid_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"video_path": "x.mp4"}))
    config = AppConfig.load(str(path))
    assert config.video_path == "x.mp4"
    assert config.frame_stride == 1  # default applied


def test_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        AppConfig.load(str(tmp_path / "does_not_exist.json"))


def test_invalid_json_exits(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json")
    with pytest.raises(SystemExit):
        AppConfig.load(str(path))


def test_invalid_field_value_exits(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"video_path": "x.mp4", "confidence_threshold": 5}))
    with pytest.raises(SystemExit):
        AppConfig.load(str(path))
