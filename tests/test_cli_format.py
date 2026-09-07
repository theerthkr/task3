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
            "ranked": [
                {
                    "similarity": 0.97,
                    "platform": "github",
                    "title": "Jane",
                    "source": "GitHub",
                    "page_url": "https://github.com/jane",
                    "has_face": True,
                    "verified": True,
                }
            ],
            "matches": [
                {
                    "similarity": 0.97,
                    "platform": "github",
                    "title": "Jane",
                    "source": "GitHub",
                    "page_url": "https://github.com/jane",
                    "has_face": True,
                    "verified": True,
                }
            ],
            "run_dir": "runs/demo",
        }
    )
    assert "https://github.com/jane" in text and "0.97" in text
    assert "Verified: 1" in text
