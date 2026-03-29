import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

APP_NAME = "sift"


def get_db_path() -> Path:
    data_dir = Path(user_data_dir(APP_NAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "sift.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS Papers (
                id           TEXT PRIMARY KEY,
                title        TEXT,
                authors      TEXT,
                abstract     TEXT,
                summary      TEXT,
                embedding    TEXT,
                cluster_id   INTEGER,
                cluster_label TEXT,
                pdf_url      TEXT,
                published_at TEXT,
                fetched_at   TEXT,
                is_read      INTEGER DEFAULT 0,
                is_saved     INTEGER DEFAULT 0,
                digest_id    TEXT
            );

            CREATE TABLE IF NOT EXISTS Digests (
                id           TEXT PRIMARY KEY,
                generated_at TEXT,
                paper_count  INTEGER,
                html_path    TEXT
            );

            CREATE TABLE IF NOT EXISTS SavedPapers (
                paper_id     TEXT,
                saved_at     TEXT,
                notes        TEXT
            );
        """)



def paper_exists(paper_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM Papers WHERE id = ?", (paper_id,)).fetchone()
        return row is not None


def insert_paper(paper: dict) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO Papers
                (id, title, authors, abstract, pdf_url, published_at, fetched_at)
            VALUES (:id, :title, :authors, :abstract, :pdf_url, :published_at, :fetched_at)
        """, {
            "id": paper["id"],
            "title": paper["title"],
            "authors": json.dumps(paper["authors"]),
            "abstract": paper["abstract"],
            "pdf_url": paper["pdf_url"],
            "published_at": paper["published_at"],
            "fetched_at": datetime.utcnow().isoformat(),
        })


def update_paper_embedding(paper_id: str, embedding: list[float]) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Papers SET embedding = ? WHERE id = ?",
            (json.dumps(embedding), paper_id),
        )


def update_paper_cluster(paper_id: str, cluster_id: int, cluster_label: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Papers SET cluster_id = ?, cluster_label = ? WHERE id = ?",
            (cluster_id, cluster_label, paper_id),
        )


def update_paper_summary(paper_id: str, summary: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Papers SET summary = ? WHERE id = ?",
            (summary, paper_id),
        )


def set_paper_digest(paper_id: str, digest_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Papers SET digest_id = ? WHERE id = ?",
            (digest_id, paper_id),
        )


def mark_paper_read(paper_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE Papers SET is_read = 1 WHERE id = ?", (paper_id,))


def save_paper(paper_id: str, notes: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE Papers SET is_saved = 1 WHERE id = ?", (paper_id,)
        )
        conn.execute(
            "INSERT OR REPLACE INTO SavedPapers (paper_id, saved_at, notes) VALUES (?, ?, ?)",
            (paper_id, datetime.utcnow().isoformat(), notes),
        )


def get_papers_without_embedding() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, abstract FROM Papers WHERE embedding IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]


def get_papers_without_summary() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, abstract FROM Papers WHERE summary IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]


def get_papers_for_digest(digest_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, authors, abstract, summary, embedding,
                      cluster_id, cluster_label, pdf_url, published_at,
                      is_read, is_saved
               FROM Papers WHERE digest_id = ?
               ORDER BY cluster_id, id""",
            (digest_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["authors"] = json.loads(d["authors"]) if d["authors"] else []
            d["embedding"] = json.loads(d["embedding"]) if d["embedding"] else []
            result.append(d)
        return result


def get_all_papers_with_embeddings() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, embedding FROM Papers WHERE embedding IS NOT NULL"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["embedding"] = json.loads(d["embedding"])
            result.append(d)
        return result


def get_unread_paper_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM Papers WHERE is_read = 0").fetchone()
        return row[0]



def create_digest(html_path: str, paper_count: int) -> str:
    digest_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO Digests (id, generated_at, paper_count, html_path) VALUES (?, ?, ?, ?)",
            (digest_id, datetime.utcnow().isoformat(), paper_count, html_path),
        )
    return digest_id


def get_latest_digest() -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM Digests ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_all_digests() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM Digests ORDER BY generated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def prune_old_digests(keep_days: int = 30) -> None:
    cutoff = datetime.utcnow().replace(microsecond=0)
    cutoff_str = cutoff.isoformat()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM Digests WHERE generated_at < datetime(?, '-' || ? || ' days')",
            (cutoff_str, keep_days),
        )



def get_saved_papers() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.id, p.title, p.authors, p.abstract, p.summary,
                   p.pdf_url, p.published_at, sp.saved_at, sp.notes
            FROM Papers p
            JOIN SavedPapers sp ON p.id = sp.paper_id
            ORDER BY sp.saved_at DESC
        """).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["authors"] = json.loads(d["authors"]) if d["authors"] else []
            result.append(d)
        return result
