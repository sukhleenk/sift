import types
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.fetcher import _parse_date, _extract_id, _parse_feed, _query_topic


# ── _parse_date ────────────────────────────────────────────────────────────────

def test_parse_date_iso_z():
    dt = _parse_date("2025-03-15T12:00:00Z")
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 3
    assert dt.day == 15
    assert dt.tzinfo == timezone.utc


def test_parse_date_iso_with_tz():
    dt = _parse_date("2025-03-15T12:00:00+00:00")
    assert dt is not None
    assert dt.year == 2025


def test_parse_date_empty():
    assert _parse_date("") is None


def test_parse_date_invalid():
    assert _parse_date("not-a-date") is None


# ── _extract_id ────────────────────────────────────────────────────────────────

def test_extract_id_standard():
    assert _extract_id("http://arxiv.org/abs/2503.12345v1") == "2503.12345"


def test_extract_id_no_version():
    assert _extract_id("http://arxiv.org/abs/2503.12345") == "2503.12345"


def test_extract_id_v2():
    assert _extract_id("http://arxiv.org/abs/2503.12345v2") == "2503.12345"


def test_extract_id_empty():
    assert _extract_id("") == ""


def test_extract_id_no_abs():
    # If there's no /abs/ the whole string is returned as-is (no crash)
    result = _extract_id("not-a-url")
    assert isinstance(result, str)


# ── _parse_feed ────────────────────────────────────────────────────────────────

def _make_entry(arxiv_id="2503.99999", title="Test Paper", published="2025-03-01T00:00:00Z"):
    entry = types.SimpleNamespace(
        id=f"http://arxiv.org/abs/{arxiv_id}v1",
        title=title,
        summary="An abstract about things.",
        published=published,
        authors=[types.SimpleNamespace(name="Alice Smith"), types.SimpleNamespace(name="Bob Jones")],
        links=[{"type": "application/pdf", "href": f"https://arxiv.org/pdf/{arxiv_id}"}],
    )
    # feedparser entries support .get() via attribute access; simulate via dict-like object
    entry.get = lambda key, default="": getattr(entry, key, default)
    return entry


def _make_feed(*entries):
    feed = MagicMock()
    feed.entries = list(entries)
    feed.bozo = False
    return feed


def test_parse_feed_basic():
    feed = _make_feed(_make_entry())
    papers = _parse_feed(feed)
    assert len(papers) == 1
    assert papers[0]["id"] == "2503.99999"
    assert papers[0]["title"] == "Test Paper"
    assert "Alice Smith" in papers[0]["authors"]


def test_parse_feed_strips_version():
    feed = _make_feed(_make_entry(arxiv_id="2503.11111"))
    papers = _parse_feed(feed)
    assert papers[0]["id"] == "2503.11111"


def test_parse_feed_empty():
    feed = _make_feed()
    assert _parse_feed(feed) == []


def test_parse_feed_multiple_entries():
    feed = _make_feed(
        _make_entry("2503.00001", "Paper A"),
        _make_entry("2503.00002", "Paper B"),
    )
    papers = _parse_feed(feed)
    assert len(papers) == 2
    ids = {p["id"] for p in papers}
    assert ids == {"2503.00001", "2503.00002"}


# ── _query_topic URL construction ──────────────────────────────────────────────

def test_query_topic_exact_phrase_url():
    captured_urls = []

    def fake_fetch(url):
        captured_urls.append(url)
        return _make_feed()

    with patch("app.fetcher._fetch_with_retry", side_effect=fake_fetch), \
         patch("app.fetcher.paper_exists", return_value=True), \
         patch("app.fetcher.insert_paper"):
        _query_topic("prompt injection", max_results=10)

    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert "%22prompt+injection%22" in url
    assert "max_results=10" in url
    assert "sortBy=submittedDate" in url
