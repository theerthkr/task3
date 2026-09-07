"""Dry run: LLM judge with mocked OpenRouter (no key, no network)."""

from unittest import mock

from face_search import llm_judge


def main() -> None:
    import json

    # bebee-style social page verdict (mocked LLM)
    payload = {"is_social_profile": True, "confidence": 0.9,
               "display_name": "Chandraveer Singh Solanki", "handle": None,
               "reason": "bebee.com people profile page for the person"}
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": json.dumps(payload)}}]}

    import os
    os.environ["OPENROUTER_API_KEY"] = "demo-key-not-real"
    with mock.patch("face_search.llm_judge.requests.post", return_value=resp):
        out = llm_judge.verdict_for_match(
            {"title": "Chandraveer Singh Solanki | Find professionals",
             "source": "BeBee", "platform": "web",
             "page_url": "https://bebee.com/in/people/chandraveer-singh-solanki",
             "similarity": 0.9944})
    print(f"llm_used={out['llm_used']} social={out['is_social_profile']} conf={out['confidence']}")
    print(f"name={out['display_name']} reason={out['reason']}")
    del os.environ["OPENROUTER_API_KEY"]

    # no key -> deterministic fallback, zero network
    out2 = llm_judge.verdict_for_match({"platform": "github", "page_url": "https://github.com/a"})
    print(f"no-key fallback: llm_used={out2['llm_used']} social={out2['is_social_profile']}")


if __name__ == "__main__":
    main()
