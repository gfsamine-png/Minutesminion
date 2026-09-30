from sentence_transformers import SentenceTransformer

# Loaded once at module import time, reused across all requests.
# all-MiniLM-L6-v2 is small (~80MB), fast, runs on CPU, and produces
# 384-dimensional embeddings — good enough quality for semantic search
# over personal notes without needing a paid embeddings API.
_model = SentenceTransformer("all-MiniLM-L6-v2")

EMBEDDING_DIMENSIONS = 384


def embed_text(text: str) -> list[float]:
    """Converts text into a 384-dimensional embedding vector.
    Used both when saving a note (embed the transcript) and when
    answering a question (embed the question itself) so they can
    be compared in the same vector space."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIMENSIONS
    vector = _model.encode(text, normalize_embeddings=True)
    return vector.tolist()