import logging
import time
from datetime import datetime, timezone

import feedparser
import requests

from app.db import insert_paper, paper_exists

logger = logging.getLogger(__name__)

_API_URL = "http://export.arxiv.org/api/query"
_USER_AGENT = "Sift/1.0 (local ArXiv digest agent)"
_TIMEOUT = 30
_DELAY_BETWEEN_TOPICS = 5   # seconds between topic requests (ArXiv ToS: >= 3s)
_RETRY_WAITS = [30, 60]     # seconds to wait before retry 1, retry 2


def fetch_papers(
    topics: list[str],
    max_per_topic: int = 30,
) -> list[dict]:
    all_papers: list[dict] = []
    seen_ids: set[str] = set()
    new_count = 0

    for i, topic in enumerate(topics):
        if i > 0:
            time.sleep(_DELAY_BETWEEN_TOPICS)

        logger.info("Fetching ArXiv papers for topic: %s", topic)
        try:
            results = _query_topic(topic, max_per_topic)
            for paper in results:
                if paper["id"] in seen_ids:
                    continue
                seen_ids.add(paper["id"])
                if paper_exists(paper["id"]):
                    logger.debug("Paper %s already in DB", paper["id"])
                else:
                    insert_paper(paper)
                    new_count += 1
                all_papers.append(paper)
        except Exception as exc:
            logger.error("Error fetching topic '%s': %s", topic, exc, exc_info=True)

    logger.info(
        "Found %d papers across %d topics (%d new)",
        len(all_papers), len(topics), new_count,
    )
    return all_papers


def _query_topic(
    topic: str,
    max_results: int,
) -> list[dict]:
    # ArXiv API uses + for spaces in query strings (not %20)
    encoded_topic = topic.strip().replace(" ", "+")
    url = (
        f"{_API_URL}"
        f"?search_query=all:{encoded_topic}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
        f"&max_results={max_results}"
        f"&start=0"
    )
    logger.info("ArXiv query: %s", url)

    feed = _fetch_with_retry(url)
    papers = _parse_feed(feed)
    logger.info("Topic '%s': %d papers found", topic, len(papers))
    return papers


def _fetch_with_retry(url: str) -> feedparser.FeedParserDict:
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt, wait_before in enumerate([0] + _RETRY_WAITS):
        if wait_before:
            logger.info("Waiting %ds before retry %d…", wait_before, attempt)
            time.sleep(wait_before)

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=_TIMEOUT,
            )

            if resp.status_code == 429:
                wait = _RETRY_WAITS[min(attempt, len(_RETRY_WAITS) - 1)]
                logger.warning("ArXiv 429 — will retry in %ds (attempt %d)", wait, attempt + 1)
                last_exc = Exception(f"HTTP 429")
                continue

            resp.raise_for_status()

            feed = feedparser.parse(resp.content)
            # bozo means parse error; but still check entries
            if feed.bozo and not feed.entries:
                raise ValueError(f"Feed parse error: {feed.bozo_exception}")

            logger.info("ArXiv returned %d entries", len(feed.entries))
            return feed

        except requests.exceptions.Timeout:
            logger.warning("Request timed out (attempt %d)", attempt + 1)
            last_exc = TimeoutError("Request timed out")
        except requests.exceptions.RequestException as exc:
            logger.warning("Request error (attempt %d): %s", attempt + 1, exc)
            last_exc = exc

    raise last_exc


def _parse_feed(feed: feedparser.FeedParserDict) -> list[dict]:
    papers = []
    for entry in feed.entries:
        try:
            published = _parse_date(entry.get("published", ""))

            arxiv_id = _extract_id(entry.get("id", ""))
            if not arxiv_id:
                continue

            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            for link in entry.get("links", []):
                if link.get("type") == "application/pdf":
                    pdf_url = link.get("href", pdf_url)
                    break

            papers.append({
                "id": arxiv_id,
                "title": entry.get("title", "").replace("\n", " ").strip(),
                "authors": [a.get("name", "") for a in entry.get("authors", [])],
                "abstract": entry.get("summary", "").replace("\n", " ").strip(),
                "pdf_url": pdf_url,
                "published_at": published.isoformat() if published else "",
            })
        except Exception as exc:
            logger.debug("Skipping malformed entry: %s", exc)

    return papers


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _extract_id(entry_id: str) -> str:
    """Extract bare arxiv ID from a URL like http://arxiv.org/abs/2503.12345v1"""
    if not entry_id:
        return ""
    bare = entry_id.split("/abs/")[-1]
    # Strip version suffix (v1, v2, …)
    if bare and "v" in bare.split(".")[-1]:
        bare = bare.rsplit("v", 1)[0]
    return bare
