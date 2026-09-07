"""Dry run: enrichment (social handle / name / company). Zero searches."""

from face_search.enrich import enrich_matches


def main() -> None:
    samples = [
        {
            "title": "Chandraveer Singh Solanki | Find professionals — Bebee",
            "source": "Bebee",
            "platform": "web",
            "page_url": "https://bebee.com/in/people/chandraveer-singh-solanki",
            "image_url": "https://example.com/i.jpg",
            "similarity": 0.9944,
        },
        {
            "title": "Jane Doe — GitHub",
            "source": "GitHub",
            "platform": "github",
            "page_url": "https://github.com/janedoe",
            "image_url": "https://example.com/i2.jpg",
            "similarity": 0.91,
        },
        {
            "title": "Jane Doe | LinkedIn",
            "source": "LinkedIn",
            "platform": "linkedin",
            "page_url": "https://www.linkedin.com/in/janedoe",
            "image_url": "https://example.com/i3.jpg",
            "similarity": 0.88,
        },
    ]
    for m in enrich_matches(samples):
        print(f"- {m['platform']}/{m.get('handle')} | {m['profile_type']} | name={m['display_name']!r} company={m['company_hint']!r}")
        print(f"  page: {m['page_url']}")


if __name__ == "__main__":
    main()
