import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_pipeline = None
_model_name: Optional[str] = None


def load_model(model_name: str) -> None:
    global _pipeline, _model_name
    if _pipeline is not None and _model_name == model_name:
        return
    logger.info("Loading summarization model: %s", model_name)
    from transformers import pipeline, AutoTokenizer

    device = _pick_device()
    _pipeline = pipeline(
        "summarization",
        model=model_name,
        device=device,
        truncation=True,
    )
    _model_name = model_name
    logger.info("Summarization model loaded on device: %s", device)


def _pick_device() -> int:
    try:
        import torch
        if torch.cuda.is_available():
            return 0
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return 0  # MPS maps to device 0 via transformers
    except Exception:
        pass
    return -1


def summarize(abstract: str) -> str:
    if _pipeline is None:
        raise RuntimeError("Summarization model not loaded. Call load_model() first.")

    max_input = 1024
    tokens = abstract.split()
    if len(tokens) > max_input:
        abstract = " ".join(tokens[:max_input])

    result = _pipeline(
        abstract,
        max_length=130,
        min_length=40,
        do_sample=False,
        truncation=True,
    )
    return result[0]["summary_text"].strip()


def summarize_and_store(papers: list[dict], model_name: str) -> None:
    from app.db import update_paper_summary

    if not papers:
        return

    load_model(model_name)

    for paper in papers:
        try:
            logger.info("Summarizing paper %s", paper["id"])
            summary = summarize(paper["abstract"])
            update_paper_summary(paper["id"], summary)
        except Exception as exc:
            logger.error("Failed to summarize %s: %s", paper["id"], exc, exc_info=True)
            # Store a placeholder so we don't retry endlessly
            update_paper_summary(paper["id"], abstract_fallback(paper["abstract"]))


def abstract_fallback(abstract: str, sentences: int = 2) -> str:
    import re
    parts = re.split(r"(?<=[.!?])\s+", abstract.strip())
    return " ".join(parts[:sentences])


def get_model_info() -> dict:
    if _pipeline is None:
        return {"loaded": False, "model_name": None, "parameters": None, "memory_mb": None}
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_mb = round(proc.memory_info().rss / (1024 ** 2), 1)
    except Exception:
        mem_mb = None
    param_count = None
    try:
        params = sum(p.numel() for p in _pipeline.model.parameters())
        param_count = f"{params / 1e6:.0f}M"
    except Exception:
        pass
    return {
        "loaded": True,
        "model_name": _model_name,
        "parameters": param_count,
        "memory_mb": mem_mb,
    }
