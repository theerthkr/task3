import json
from pathlib import Path

from face_search.serp_client import _CANDIDATE_FIELDS, parse_results


def _sample():
    return json.loads(Path("tests/fixtures/lens_sample.json").read_text())


def test_parse_merges_visual_and_exact_matches():
    out = parse_results(_sample())
    assert len(out) == 2
    assert out[0]["page_url"] == "https://example.com/talk"
    assert out[0]["match_kind"] == "visual_matches"
    assert out[1]["page_url"] == "https://linkedin.com/in/janedoe"
    assert out[1]["match_kind"] == "exact_matches"
    assert set(out[0]) == set(_CANDIDATE_FIELDS)
    assert all(row["engine"] == "google_lens" for row in out)


def test_parse_empty_response():
    assert parse_results({}) == []
