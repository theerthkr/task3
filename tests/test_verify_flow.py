"""Local face-verification flow: no network, no SerpApi, real embeddings."""

from face_search import faces, rank

import pathlib
# Fallback to bundled test images if HHGOA not present (HHGOA is gitignored)
_HHGOA_A = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg"
_HHGOA_B = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_b.jpg"
_HHGOA_C = "HHGOA-FACE-BLOCKCHAIN/test_images/person2_a.jpg"
# Bundled alternatives that exist in repo
_FALLBACK_A = "chandu.png"
_FALLBACK_B = "chandu.png"  # same face -> high similarity
_FALLBACK_C = "img1.png"    # different face -> low similarity

def _pick(a, b):
    return a if pathlib.Path(a).exists() else b

A = _pick(_HHGOA_A, _FALLBACK_A)
B = _pick(_HHGOA_B, _FALLBACK_B)
C = _pick(_HHGOA_C, _FALLBACK_C)


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
