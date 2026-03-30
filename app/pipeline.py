import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from platformdirs import user_log_dir

APP_NAME = "sift"
logger = logging.getLogger(__name__)

# Pipeline state
_running = False
_lock = threading.Lock()


def is_running() -> bool:
    return _running


def run_pipeline(
    config: dict,
    on_complete: Optional[Callable[[str, int], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> None:
    global _running
    with _lock:
        if _running:
            logger.warning("Pipeline already running — skipping duplicate trigger.")
            return
        _running = True

    thread = threading.Thread(
        target=_pipeline_worker,
        args=(config, on_complete, on_error),
        daemon=True,
    )
    thread.start()


def _pipeline_worker(
    config: dict,
    on_complete: Optional[Callable],
    on_error: Optional[Callable],
) -> None:
    global _running
    t_start = time.monotonic()
    try:
        _run_all_steps(config, t_start, on_complete)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        if on_error:
            try:
                on_error(exc)
            except Exception:
                pass
    finally:
        with _lock:
            _running = False


def _run_all_steps(
    config: dict,
    t_start: float,
    on_complete: Optional[Callable],
) -> None:
    from app import db, fetcher, embedder, clusterer, summarizer, renderer

    db.init_db()

    topics: list[str] = config.get("topics", [])
    hours_back: int = config.get("hours_back", 24)
    max_papers: int = config.get("max_papers", 10)
    sum_model: str = config["summarization_model"]
    emb_model: str = config["embedding_model"]
    retention: int = config.get("digest_retention_days", 30)

    logger.info("[Pipeline] Step 1 — Fetch")
    t0 = time.monotonic()
    new_papers = fetcher.fetch_papers(topics, max_per_topic=max_papers * 2)
    logger.info("[Pipeline] Found %d papers in %.1fs", len(new_papers), time.monotonic() - t0)

    if not new_papers:
        logger.info("[Pipeline] No papers found — skipping digest generation.")
        return

    new_papers = new_papers[:max_papers]

    logger.info("[Pipeline] Step 2 — Embed")
    t0 = time.monotonic()
    papers_needing_embed = db.get_papers_without_embedding()
    current_ids = {p["id"] for p in new_papers}
    to_embed = [p for p in papers_needing_embed if p["id"] in current_ids]
    embedder.embed_and_store(to_embed, emb_model)
    logger.info("[Pipeline] Embedded %d papers in %.1fs", len(to_embed), time.monotonic() - t0)

    all_with_emb = db.get_all_papers_with_embeddings()
    current_with_emb = [p for p in all_with_emb if p["id"] in current_ids]

    paper_detail = {p["id"]: p for p in new_papers}
    for p in current_with_emb:
        if p["id"] in paper_detail:
            p["abstract"] = paper_detail[p["id"]]["abstract"]

    if not current_with_emb:
        logger.warning("[Pipeline] No embeddings available — cannot cluster.")
        return

    logger.info("[Pipeline] Step 3 — Cluster")
    t0 = time.monotonic()
    sorted_papers = clusterer.cluster_papers(current_with_emb)
    logger.info("[Pipeline] Clustered %d papers in %.1fs", len(sorted_papers), time.monotonic() - t0)

    logger.info("[Pipeline] Step 4 — Summarize")
    t0 = time.monotonic()
    db_missing = db.get_papers_without_summary()
    missing_ids = {p["id"] for p in db_missing} & current_ids
    to_summarize = [p for p in sorted_papers if p["id"] in missing_ids]
    summarizer.summarize_and_store(to_summarize, sum_model)
    logger.info("[Pipeline] Summarized %d papers in %.1fs", len(to_summarize), time.monotonic() - t0)

    digest_id_placeholder = "pending"
    final_papers = _assemble_papers(sorted_papers, current_ids)

    logger.info("[Pipeline] Step 5 — Render")
    t0 = time.monotonic()
    generation_seconds = time.monotonic() - t_start
    html_path = renderer.render_digest(
        final_papers, topics, "tmp", generation_seconds
    )

    digest_id = db.create_digest(html_path, len(final_papers))

    from pathlib import Path as _Path
    final_html_path = renderer.render_digest(
        final_papers, topics, digest_id, generation_seconds
    )
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE Digests SET html_path = ? WHERE id = ?",
            (final_html_path, digest_id),
        )

    tmp = _Path(html_path)
    if tmp.exists():
        tmp.unlink(missing_ok=True)

    for p in final_papers:
        db.set_paper_digest(p["id"], digest_id)

    db.prune_old_digests(retention)

    logger.info(
        "[Pipeline] Complete — %d papers, digest %s, HTML at %s (%.1fs total)",
        len(final_papers), digest_id, final_html_path, time.monotonic() - t_start,
    )

    if on_complete:
        try:
            on_complete(final_html_path, len(final_papers))
        except Exception:
            pass


def _assemble_papers(sorted_papers: list[dict], current_ids: set[str]) -> list[dict]:
    from app.db import get_connection
    import json as _json

    id_to_cluster = {p["id"]: (p.get("cluster_id"), p.get("cluster_label")) for p in sorted_papers}
    order = [p["id"] for p in sorted_papers]

    with get_connection() as conn:
        placeholders = ",".join("?" * len(current_ids))
        rows = conn.execute(
            f"""SELECT id, title, authors, abstract, summary, pdf_url,
                       published_at, is_read, is_saved
                FROM Papers WHERE id IN ({placeholders})""",
            list(current_ids),
        ).fetchall()

    by_id = {}
    for r in rows:
        d = dict(r)
        d["authors"] = _json.loads(d["authors"]) if d["authors"] else []
        cid, clabel = id_to_cluster.get(d["id"], (0, "miscellaneous"))
        d["cluster_id"] = cid
        d["cluster_label"] = clabel
        by_id[d["id"]] = d

    return [by_id[pid] for pid in order if pid in by_id]
