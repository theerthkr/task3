"""Local face-verification flow: no network, no SerpApi, real embeddings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face_search import faces, rank

A = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg"
B = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_b.jpg"
C = "HHGOA-FACE-BLOCKCHAIN/test_images/person2_a.jpg"


def test_same_face_scores_above_threshold():
    query = faces.largest_embedding(A)
    same = faces.largest_embedding(B)
    assert faces.cosine(query, same) >= 0.45


def test_other_face_scores_below_threshold():
    query = faces.largest_embedding(A)
    other = faces.largest_embedding(C)
    assert faces.cosine(query, other) < 0.45


def test_ranking_prefers_matching_social_source():
    query = faces.largest_embedding(A)
    items = [
        {
            "page_url": "https://example.com/other",
            "similarity": faces.cosine(query, faces.largest_embedding(C)),
            "has_face": True,
        },
        {
            "page_url": "https://github.com/someone",
            "similarity": faces.cosine(query, faces.largest_embedding(B)),
            "has_face": True,
        },
    ]
    ordered = rank.rank_candidates(items, threshold=0.45)
    assert [row["page_url"] for row in ordered] == ["https://github.com/someone"]
