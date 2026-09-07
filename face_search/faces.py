"""Face embeddings via InsightFace. Lazy singleton: no model load on import."""

import cv2
import numpy as np

from face_search import config

_engine = None


def _get_app():
    global _engine
    if _engine is None:
        from insightface.app import FaceAnalysis

        _engine = FaceAnalysis(
            name=config.FACE_MODEL_PACK,
            root=str(config.PROJECT_ROOT / ".insightface_cache"),
        )
        _engine.prepare(ctx_id=-1, det_size=config.FACE_DET_SIZE)
    return _engine


def largest_embedding(image_path: str):
    """Embedding of the largest face, L2-normalized. None when no face found."""
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path!r}")
    faces = _get_app().get(image)
    if not faces:
        return None
    face = max(faces, key=lambda found: _area(found.bbox))
    vector = face.normed_embedding.astype(np.float64)
    return vector / np.linalg.norm(vector)


def _area(bbox) -> float:
    return float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))


def cosine(first, second) -> float:
    return float(np.dot(first, second))
