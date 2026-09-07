import pytest

from face_search.enrich import enrich_match, extract_display_name, extract_handle


def test_handle_github():
    assert extract_handle("https://github.com/janedoe/repo") == "janedoe"


def test_handle_x_twitter_instagram():
    assert extract_handle("https://x.com/jane_doe/status/1") == "jane_doe"
    assert extract_handle("https://twitter.com/jane") == "jane"
    assert extract_handle("https://instagram.com/jane.doe/") == "jane.doe"


def test_handle_linkedin():
    assert extract_handle("https://www.linkedin.com/in/janedoe") == "janedoe"
    assert extract_handle("https://www.linkedin.com/company/acme") == "acme"


def test_handle_web_returns_none():
    assert extract_handle("https://example.com/a") is None
    assert extract_handle("https://bebee.com/in/people/jane") is None


def test_display_name_split():
    name, company = extract_display_name("Chandraveer Singh Solanki | Find professionals — Bebee")
    assert name == "Chandraveer Singh Solanki"
    assert company == "Find professionals — Bebee"


def test_enrich_social_profile():
    m = {
        "title": "Jane Doe | GitHub",
        "source": "GitHub",
        "platform": "github",
        "page_url": "https://github.com/janedoe",
        "image_url": "https://example.com/i.jpg",
        "similarity": 0.97,
    }
    out = enrich_match(m)
    assert out["handle"] == "janedoe"
    assert out["profile_type"] == "social_profile"
    assert out["is_social"] is True


def test_enrich_web_page():
    m = {
        "title": "RAJ BHATTACHARYYA | Devfolio",
        "source": "Devfolio",
        "platform": "web",
        "page_url": "https://acehack.devfolio.co/@Raj4/projects",
        "image_url": "https://example.com/i.jpg",
        "similarity": 0.97,
    }
    out = enrich_match(m)
    assert out["handle"] is None
    assert out["profile_type"] == "web_page"
    assert out["display_name"] == "RAJ BHATTACHARYYA"
