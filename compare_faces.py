#!/usr/bin/env python3
"""
Compare two images using the existing face verification module.

Usage:
    python compare_faces.py <image1> <image2> [--threshold T]

Outputs:
    Prints the cosine similarity and whether the faces match (similarity >= threshold).
"""

import sys
from pathlib import Path

# Ensure the face_search module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from face_search.faces import largest_embedding, cosine


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    img1_path = sys.argv[1]
    img2_path = sys.argv[2]
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] == '--threshold' and len(sys.argv) > 4 else 0.45
    # Simple threshold parsing: if the third arg is --threshold, use the fourth; else if there are exactly 3 args, use default.
    # For simplicity, we'll do:
    #   If there are 4 or more args and the third is --threshold, use fourth as threshold.
    #   Otherwise, if there are exactly 3 args, use default threshold.
    #   If there are more than 3 args but not matching the pattern, ignore extra.
    # Let's redo the argument parsing more clearly.

    # Re-parse:
    args = sys.argv[1:]
    img1_path = args[0]
    img2_path = args[1]
    threshold = 0.45
    if len(args) >= 3 and args[2] == '--threshold':
        if len(args) >= 4:
            try:
                threshold = float(args[3])
            except ValueError:
                print("Error: threshold must be a number")
                sys.exit(1)
        else:
            print("Error: --threshold requires a value")
            sys.exit(1)
    # Ignore any extra arguments

    try:
        emb1 = largest_embedding(img1_path)
        if emb1 is None:
            print(f"Error: No face detected in {img1_path}")
            sys.exit(1)
    except Exception as e:
        print(f"Error processing {img1_path}: {e}")
        sys.exit(1)

    try:
        emb2 = largest_embedding(img2_path)
        if emb2 is None:
            print(f"Error: No face detected in {img2_path}")
            sys.exit(1)
    except Exception as e:
        print(f"Error processing {img2_path}: {e}")
        sys.exit(1)

    sim = cosine(emb1, emb2)
    match = sim >= threshold

    print(f"Similarity: {sim:.6f}")
    print(f"Threshold: {threshold}")
    print(f"Match: {match}")

if __name__ == "__main__":
    main()