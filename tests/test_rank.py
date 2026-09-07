from face_search.rank import is_social, platform_of, rank_candidates


def test_platform_detection():
    assert platform_of("https://www.linkedin.com/in/jane") == "linkedin"
    assert platform_of("https://x.com/jane/status/1") == "x"
    assert platform_of("https://sub.github.com/jane") == "github"
    assert platform_of("https://example.com/a") == "web"
    assert is_social("https://instagram.com/jane") is True
    assert is_social("https://example.com/a") is False


def test_social_boost_and_threshold():
    items = [
        {"page_url": "https://example.com/a", "similarity": 0.9, "has_face": True},
        {"page_url": "https://github.com/jane", "similarity": 0.6, "has_face": True},
        {"page_url": "https://example.com/b", "similarity": 0.2, "has_face": True},
        {"page_url": "https://example.com/c", "similarity": 0.8, "has_face": False},
    ]
    out = rank_candidates(items, threshold=0.45)
    assert [row["page_url"] for row in out] == [
        "https://github.com/jane",
        "https://example.com/a",
    ]


def test_dedupe_keeps_best_similarity():
    items = [
        {"page_url": "https://example.com/a", "similarity": 0.5, "has_face": True},
        {"page_url": "https://example.com/a", "similarity": 0.7, "has_face": True},
    ]
    out = rank_candidates(items, threshold=0.45)
    assert len(out) == 1 and out[0]["similarity"] == 0.7
