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


def _reset_engine() -> None:
    """Test hook: drop the cached model so the next call reloads it."""
    global _engine
    _engine = None


def detect(image_path: str) -> list:
    """All face embeddings in an image, largest face first, L2-normalized."""
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path!r}")
    faces = sorted(_get_app().get(image), key=lambda found: _area(found.bbox))
    return [_normalized(face.normed_embedding) for face in reversed(faces)]


def largest_embedding(image_path: str):
    """Embedding of the largest face. None when no face found."""
    found = detect(image_path)
    return found[0] if found else None


def _normalized(vector):
    vector = vector.astype(np.float64)
    return vector / np.linalg.norm(vector)


def _area(bbox) -> float:
    return float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))


def cosine(first, second) -> float:
    """Cosine similarity of two L2-normalized embeddings from detect()."""
    return float(np.dot(first, second))
