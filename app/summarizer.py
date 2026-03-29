import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_model_state: Optional[dict] = None  # {"tokenizer": ..., "model": ..., "device": ...}
_model_name: Optional[str] = None


def load_model(model_name: str) -> None:
    global _model_state, _model_name
    if _model_state is not None and _model_name == model_name:
        return
    logger.info("Loading summarization model: %s", model_name)
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

    device = _pick_device()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model = model.to(device)
    model.eval()
    _model_state = {"tokenizer": tokenizer, "model": model, "device": device}
    _model_name = model_name
    logger.info("Summarization model loaded on device: %s", device)


def _pick_device():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
    except Exception:
        pass
    import torch
    return torch.device("cpu")


def summarize(abstract: str) -> str:
    if _model_state is None:
        raise RuntimeError("Summarization model not loaded. Call load_model() first.")

    import torch
    tokenizer = _model_state["tokenizer"]
    model = _model_state["model"]
    device = _model_state["device"]

    max_input_tokens = 1024
    tokens = abstract.split()
    if len(tokens) > max_input_tokens:
        abstract = " ".join(tokens[:max_input_tokens])

    inputs = tokenizer(
        abstract, return_tensors="pt", truncation=True, max_length=1024
    ).to(device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_length=130,
            min_length=40,
            num_beams=4,
            early_stopping=True,
        )
    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()


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
    if _model_state is None:
        return {"loaded": False, "model_name": None, "parameters": None, "memory_mb": None}
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_mb = round(proc.memory_info().rss / (1024 ** 2), 1)
    except Exception:
        mem_mb = None
    param_count = None
    try:
        params = sum(p.numel() for p in _model_state["model"].parameters())
        param_count = f"{params / 1e6:.0f}M"
    except Exception:
        pass
    return {
        "loaded": True,
        "model_name": _model_name,
        "parameters": param_count,
        "memory_mb": mem_mb,
    }
