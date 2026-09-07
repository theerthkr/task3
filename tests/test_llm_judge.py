from unittest import mock

from face_search import llm_judge


def _llm_response(payload):
    import json

    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": json.dumps(payload)}}]}
    return resp


def test_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = llm_judge.verdict_for_match({"platform": "github", "page_url": "https://github.com/a"})
    assert out["llm_used"] is False and out["is_social_profile"] is True


def test_live_verdict_parsed(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    payload = {"is_social_profile": True, "confidence": 0.92, "display_name": "Jane",
               "handle": "janedoe", "reason": "linkedin.com/in profile page"}
    with mock.patch("face_search.llm_judge.requests.post", return_value=_llm_response(payload)):
        out = llm_judge.verdict_for_match({"title": "Jane | LinkedIn", "platform": "linkedin",
                                           "page_url": "https://linkedin.com/in/janedoe"})
    assert out["llm_used"] is True and out["handle"] == "janedoe"


def test_http_error_falls_back(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    resp = mock.Mock()
    resp.status_code = 401
    with mock.patch("face_search.llm_judge.requests.post", return_value=resp):
        out = llm_judge.verdict_for_match({"platform": "web", "page_url": "https://example.com"})
    assert out["llm_used"] is False and out["is_social_profile"] is False
