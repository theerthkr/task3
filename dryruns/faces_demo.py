"""Dry run: real InsightFace embeddings on local test photos. Zero searches."""

from face_search import faces

A = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_a.jpg"
B = "HHGOA-FACE-BLOCKCHAIN/test_images/person1_b.jpg"
C = "HHGOA-FACE-BLOCKCHAIN/test_images/person2_a.jpg"


def main() -> None:
    print(f"faces in A: {len(faces.detect(A))}")
    print(f"faces in C: {len(faces.detect(C))}")
    query = faces.largest_embedding(A)
    same = faces.cosine(query, faces.largest_embedding(B))
    other = faces.cosine(query, faces.largest_embedding(C))
    print(f"same-photo similarity : {same:.4f} (threshold 0.45 -> match)")
    print(f"cross-person similarity: {other:.4f} (threshold 0.45 -> no match)")


if __name__ == "__main__":
    main()
