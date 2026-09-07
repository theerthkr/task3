import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face_search.key_store import load_key


def test_loads_raw_key_file(tmp_path):
    (tmp_path / "api_key.json").write_text("SAMPLE_KEY_123")
    assert load_key(search_dir=tmp_path, env={}) == "SAMPLE_KEY_123"


def test_loads_json_object_key_file(tmp_path):
    (tmp_path / "api_key.json").write_text('{"api_key": "OBJ_KEY"}')
    assert load_key(search_dir=tmp_path, env={}) == "OBJ_KEY"


def test_env_takes_precedence(tmp_path):
    (tmp_path / "api_key.json").write_text("FILE_KEY")
    assert load_key(search_dir=tmp_path, env={"SERPAPI_KEY": "ENV_KEY"}) == "ENV_KEY"


def test_missing_key_raises(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        load_key(search_dir=tmp_path, env={})


def test_loads_env_assignment_style(tmp_path):
    (tmp_path / "api_key.json").write_text('SERP_API_KEY="ABC123"')
    assert load_key(search_dir=tmp_path, env={}) == "ABC123"


def test_loads_unquoted_assignment_style(tmp_path):
    (tmp_path / "api_key.json").write_text("SERPAPI_KEY=XYZ789")
    assert load_key(search_dir=tmp_path, env={}) == "XYZ789"
