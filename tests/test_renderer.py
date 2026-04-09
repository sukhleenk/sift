import pytest
from unittest.mock import patch
from pathlib import Path

from app.renderer import _format_duration, _build_clusters, render_digest, render_saved_papers


# ── _format_duration ───────────────────────────────────────────────────────────

def test_format_duration_seconds():
    assert _format_duration(45.7) == "46s"


def test_format_duration_minutes():
    assert _format_duration(90.0) == "1m 30s"


def test_format_duration_zero():
    assert _format_duration(0.0) == "0s"


# ── _build_clusters ────────────────────────────────────────────────────────────

def _make_paper(arxiv_id, cluster_id=0, label="ml"):
    return {
        "id": arxiv_id,
        "title": f"Paper {arxiv_id}",
        "authors": ["Alice"],
        "abstract": "Some abstract text.",
        "summary": "A summary.",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "published_at": "2025-03-01T00:00:00+00:00",
        "cluster_id": cluster_id,
        "cluster_label": label,
        "is_read": False,
        "is_saved": False,
    }


def test_build_clusters_single_cluster():
    papers = [_make_paper("2503.00001"), _make_paper("2503.00002")]
    clusters = _build_clusters(papers)
    assert len(clusters) == 1
    assert clusters[0]["id"] == 0
    assert len(clusters[0]["papers"]) == 2


def test_build_clusters_multiple():
    papers = [_make_paper("2503.00001", cluster_id=0, label="nlp"),
              _make_paper("2503.00002", cluster_id=1, label="cv")]
    clusters = _build_clusters(papers)
    assert len(clusters) == 2
    labels = {c["label"] for c in clusters}
    assert labels == {"nlp", "cv"}


def test_build_clusters_date_display():
    papers = [_make_paper("2503.00001")]
    clusters = _build_clusters(papers)
    paper = clusters[0]["papers"][0]
    assert "2025" in paper["date_display"]


# ── render_digest ──────────────────────────────────────────────────────────────

def test_render_digest_produces_html(tmp_path):
    papers = [_make_paper("2503.00001")]

    with patch("app.renderer._output_dir", return_value=tmp_path):
        html_path = render_digest(papers, topics=["machine learning"], digest_id="test", generation_seconds=5.0, action_port=9999)

    assert Path(html_path).exists()
    content = Path(html_path).read_text()
    assert "Paper 2503.00001" in content
    assert "machine learning" in content


def test_render_digest_contains_action_port(tmp_path):
    papers = [_make_paper("2503.00001")]

    with patch("app.renderer._output_dir", return_value=tmp_path):
        html_path = render_digest(papers, topics=["llm"], digest_id="test2", generation_seconds=1.0, action_port=12345)

    content = Path(html_path).read_text()
    assert "12345" in content


# ── render_saved_papers ────────────────────────────────────────────────────────

def test_render_saved_papers_as_string():
    papers = [{
        "id": "2503.00005",
        "title": "Saved Paper",
        "authors": ["Bob"],
        "abstract": "Abstract here.",
        "summary": "Summary.",
        "pdf_url": "https://arxiv.org/pdf/2503.00005",
        "published_at": "2025-03-01T00:00:00+00:00",
        "saved_at": "2025-03-02T00:00:00+00:00",
        "notes": "interesting",
    }]
    html = render_saved_papers(papers, action_port=8888, as_string=True)
    assert "Saved Paper" in html
    assert "8888" in html
    assert "interesting" in html


def test_render_saved_papers_empty():
    html = render_saved_papers([], action_port=0, as_string=True)
    assert "No saved papers" in html
