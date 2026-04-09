import json
import os
import tempfile
import pytest
from unittest.mock import patch
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    db_file = tmp_path / "test.db"
    import app.db  # ensure module is in sys.modules before patch resolves it
    with patch("app.db.get_db_path", return_value=db_file):
        from app import db
        db.init_db()
        yield db


def test_init_db_creates_tables(temp_db):
    with temp_db.get_connection() as conn:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"Papers", "Digests", "SavedPapers"}.issubset(tables)


def test_paper_does_not_exist(temp_db):
    assert temp_db.paper_exists("9999.99999") is False


def test_insert_and_exists(temp_db):
    paper = {
        "id": "2503.12345",
        "title": "Test Paper",
        "authors": ["Alice", "Bob"],
        "abstract": "An abstract.",
        "pdf_url": "https://arxiv.org/pdf/2503.12345",
        "published_at": "2025-03-01T00:00:00+00:00",
    }
    temp_db.insert_paper(paper)
    assert temp_db.paper_exists("2503.12345") is True


def test_insert_is_idempotent(temp_db):
    paper = {
        "id": "2503.00001",
        "title": "Dup",
        "authors": [],
        "abstract": "",
        "pdf_url": "",
        "published_at": "",
    }
    temp_db.insert_paper(paper)
    temp_db.insert_paper(paper)
    with temp_db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM Papers WHERE id=?", ("2503.00001",)).fetchone()[0]
    assert count == 1


def test_update_embedding(temp_db):
    paper = {"id": "2503.00002", "title": "", "authors": [], "abstract": "", "pdf_url": "", "published_at": ""}
    temp_db.insert_paper(paper)
    temp_db.update_paper_embedding("2503.00002", [0.1, 0.2, 0.3])
    with temp_db.get_connection() as conn:
        row = conn.execute("SELECT embedding FROM Papers WHERE id=?", ("2503.00002",)).fetchone()
    assert json.loads(row[0]) == [0.1, 0.2, 0.3]


def test_update_summary(temp_db):
    paper = {"id": "2503.00003", "title": "", "authors": [], "abstract": "", "pdf_url": "", "published_at": ""}
    temp_db.insert_paper(paper)
    temp_db.update_paper_summary("2503.00003", "A summary.")
    with temp_db.get_connection() as conn:
        row = conn.execute("SELECT summary FROM Papers WHERE id=?", ("2503.00003",)).fetchone()
    assert row[0] == "A summary."


def test_mark_paper_read(temp_db):
    paper = {"id": "2503.00004", "title": "", "authors": [], "abstract": "", "pdf_url": "", "published_at": ""}
    temp_db.insert_paper(paper)
    temp_db.mark_paper_read("2503.00004")
    with temp_db.get_connection() as conn:
        row = conn.execute("SELECT is_read FROM Papers WHERE id=?", ("2503.00004",)).fetchone()
    assert row[0] == 1


def test_save_paper(temp_db):
    paper = {"id": "2503.00005", "title": "", "authors": [], "abstract": "", "pdf_url": "", "published_at": ""}
    temp_db.insert_paper(paper)
    temp_db.save_paper("2503.00005", notes="interesting")
    saved = temp_db.get_saved_papers()
    assert any(p["id"] == "2503.00005" for p in saved)


def test_get_papers_without_embedding(temp_db):
    paper = {"id": "2503.00006", "title": "", "authors": [], "abstract": "text", "pdf_url": "", "published_at": ""}
    temp_db.insert_paper(paper)
    missing = temp_db.get_papers_without_embedding()
    assert any(p["id"] == "2503.00006" for p in missing)
    temp_db.update_paper_embedding("2503.00006", [1.0])
    missing = temp_db.get_papers_without_embedding()
    assert not any(p["id"] == "2503.00006" for p in missing)


def test_create_and_get_digest(temp_db):
    digest_id = temp_db.create_digest("/tmp/digest.html", 5)
    latest = temp_db.get_latest_digest()
    assert latest["id"] == digest_id
    assert latest["paper_count"] == 5


def test_get_unread_count(temp_db):
    for i in range(3):
        paper = {"id": f"2503.1000{i}", "title": "", "authors": [], "abstract": "", "pdf_url": "", "published_at": ""}
        temp_db.insert_paper(paper)
    assert temp_db.get_unread_paper_count() == 3
    temp_db.mark_paper_read("2503.10000")
    assert temp_db.get_unread_paper_count() == 2
