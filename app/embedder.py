import logging
from typing import Optional

logger = logging.getLogger(__name__)

_model = None
_model_name: Optional[str] = None


def load_model(model_name: str) -> None:
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return
    logger.info("Loading embedding model: %s", model_name)
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(model_name)
    _model_name = model_name
    logger.info("Embedding model loaded.")


def embed_texts(texts: list[str]) -> list[list[float]]:
    if _model is None:
        raise RuntimeError("Embedding model not loaded. Call load_model() first.")
    embeddings = _model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_and_store(papers: list[dict], model_name: str) -> None:
    from app.db import update_paper_embedding

    if not papers:
        return

    load_model(model_name)

    ids = [p["id"] for p in papers]
    abstracts = [p["abstract"] for p in papers]

    logger.info("Embedding %d abstracts with %s", len(abstracts), model_name)
    embeddings = embed_texts(abstracts)

    for paper_id, embedding in zip(ids, embeddings):
        update_paper_embedding(paper_id, embedding)

    logger.info("Embeddings stored for %d papers.", len(papers))


def get_model_info() -> dict:
    if _model is None:
        return {"loaded": False, "model_name": None, "memory_mb": None}
    import os
    import psutil
    proc = psutil.Process(os.getpid())
    mem_mb = proc.memory_info().rss / (1024 ** 2)
    return {
        "loaded": True,
        "model_name": _model_name,
        "memory_mb": round(mem_mb, 1),
    }
