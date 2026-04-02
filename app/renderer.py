import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

APP_NAME = "sift"
TEMPLATE_NAME = "digest.html.j2"


def _templates_dir() -> Path:
    # Support both installed package and running from repo root
    here = Path(__file__).parent.parent / "templates"
    if here.exists():
        return here
    raise FileNotFoundError(f"Templates directory not found: {here}")


def _output_dir() -> Path:
    # Use ~/Documents/Sift so snap-sandboxed browsers (e.g. Firefox snap) can
    # open the files.  ~/.local/share is outside the snap's AppArmor profile.
    out = Path.home() / "Documents" / "Sift"
    out.mkdir(parents=True, exist_ok=True)
    return out


def render_digest(
    papers: list[dict],
    topics: list[str],
    digest_id: str,
    generation_seconds: float,
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tojson"] = _paper_tojson

    template = env.get_template(TEMPLATE_NAME)

    clusters = _build_clusters(papers)

    now = datetime.now(timezone.utc)
    date_label = now.strftime("%A, %B %-d")  # e.g. "Saturday, March 28"
    read_count = sum(1 for p in papers if p.get("is_read"))

    gen_time = _format_duration(generation_seconds)

    context = {
        "date_label": date_label,
        "total_papers": len(papers),
        "read_count": read_count,
        "topics": topics,
        "clusters": clusters,
        "generation_time": gen_time,
    }

    html = template.render(**context)

    output_path = _output_dir() / f"digest_{digest_id}.html"
    output_path.write_text(html, encoding="utf-8")
    logger.info("Digest rendered to %s", output_path)
    return str(output_path)


def _build_clusters(papers: list[dict]) -> list[dict]:
    seen: list[int] = []
    cluster_map: dict[int, dict] = {}

    for paper in papers:
        cid = paper.get("cluster_id", 0)
        label = paper.get("cluster_label", "miscellaneous")
        if cid not in cluster_map:
            seen.append(cid)
            cluster_map[cid] = {"id": cid, "label": label, "papers": []}

        published = paper.get("published_at", "")
        try:
            dt = datetime.fromisoformat(published)
            date_display = dt.strftime("%b %-d %Y")
        except Exception:
            date_display = published[:10]

        cluster_map[cid]["papers"].append({
            "id": paper["id"],
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "abstract": paper.get("abstract", ""),
            "summary": paper.get("summary") or "",
            "pdf_url": paper.get("pdf_url", ""),
            "published_at": published,
            "date_display": date_display,
            "category": _extract_category(paper.get("id", "")),
            "is_read": bool(paper.get("is_read")),
            "is_saved": bool(paper.get("is_saved")),
        })

    return [cluster_map[cid] for cid in seen]


def _extract_category(arxiv_id: str) -> str:
    """Best-effort: arxiv IDs like 2503.12345 don't carry category inline."""
    return "arXiv"


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"


def _paper_tojson(paper: dict) -> str:
    safe = {
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "published_at": paper.get("published_at", ""),
    }
    return json.dumps(safe)
