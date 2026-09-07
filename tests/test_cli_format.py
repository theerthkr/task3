from face_search.cli import format_report


def test_formats_dry_run():
    text = format_report(
        {
            "mode": "DRY_RUN",
            "searches_spent": 0,
            "query": {"path": "face.jpg", "faces_found": 1},
            "matches": [],
            "candidates_found": 0,
            "verified": 0,
            "run_dir": "runs/demo",
        }
    )
    assert "DRY_RUN" in text and "face.jpg" in text


def test_formats_matches():
    text = format_report(
        {
            "mode": "LIVE",
            "searches_spent": 1,
            "query": {"path": "face.jpg", "faces_found": 1, "hosted_url": "https://imgops.com/1hr-tempcache/a.jpg"},
            "candidates_found": 2,
            "verified": 1,
            "matches": [
                {
                    "similarity": 0.97,
                    "platform": "github",
                    "title": "Jane",
                    "page_url": "https://github.com/jane",
                    "handle": "jane",
                    "profile_type": "social_profile",
                    "is_social": True,
                    "display_name": "Jane",
                    "company_hint": None,
                }
            ],
            "run_dir": "runs/demo",
        }
    )
    assert "https://github.com/jane" in text and "0.97" in text
    assert "social_profile" in text
