import logging
from typing import Optional

import numpy as np
from joblib import parallel_backend
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def cluster_papers(papers: list[dict]) -> list[dict]:
    if not papers:
        return papers

    n = len(papers)
    k = max(2, min(5, n // 2))

    embeddings = np.array([p["embedding"] for p in papers], dtype=np.float32)

    logger.info("Running k-means with k=%d on %d papers", k, n)
    km = KMeans(n_clusters=k, random_state=42, n_init="auto")
    with parallel_backend("threading"):
        labels = km.fit_predict(embeddings)
    centroids = km.cluster_centers_

    cluster_labels = _label_clusters(papers, embeddings, labels, centroids, k)
    cluster_order = _rank_clusters(papers, labels)

    for paper, label_idx in zip(papers, labels):
        paper["cluster_id"] = int(label_idx)
        paper["cluster_label"] = cluster_labels[int(label_idx)]

    from app.db import update_paper_cluster
    for paper in papers:
        update_paper_cluster(paper["id"], paper["cluster_id"], paper["cluster_label"])

    return _sort_papers(papers, embeddings, labels, centroids, cluster_order)


def _label_clusters(
    papers: list[dict],
    embeddings: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
    k: int,
) -> dict[int, str]:
    cluster_labels = {}
    for cluster_id in range(k):
        indices = np.where(labels == cluster_id)[0]
        if len(indices) == 0:
            cluster_labels[cluster_id] = f"cluster {cluster_id}"
            continue

        cluster_embs = embeddings[indices]
        centroid = centroids[cluster_id].reshape(1, -1)
        sims = cosine_similarity(cluster_embs, centroid).flatten()
        top_n = min(3, len(indices))
        top_indices = indices[np.argsort(sims)[::-1][:top_n]]

        combined_text = " ".join(papers[i]["abstract"] for i in top_indices)
        label = _tfidf_label(combined_text)
        cluster_labels[cluster_id] = label

    return cluster_labels


def _tfidf_label(text: str, top_n: int = 4) -> str:
    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=200,
            ngram_range=(1, 2),
        )
        vectorizer.fit([text])
        feature_array = np.array(vectorizer.get_feature_names_out())
        tfidf_scores = vectorizer.transform([text]).toarray().flatten()
        top_indices = np.argsort(tfidf_scores)[::-1][:top_n]
        terms = feature_array[top_indices]
        return " / ".join(t for t in terms if t)
    except Exception:
        return "miscellaneous"


def _rank_clusters(papers: list[dict], labels: np.ndarray) -> list[int]:
    from collections import Counter
    counts = Counter(labels.tolist())
    ordered = sorted(counts.keys(), key=lambda c: counts[c], reverse=True)
    return ordered


def _sort_papers(
    papers: list[dict],
    embeddings: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
    cluster_order: list[int],
) -> list[dict]:
    cluster_rank = {cid: rank for rank, cid in enumerate(cluster_order)}

    sims_per_cluster: dict[int, np.ndarray] = {}
    for cluster_id in set(labels.tolist()):
        indices = np.where(labels == cluster_id)[0]
        cluster_embs = embeddings[indices]
        centroid = centroids[cluster_id].reshape(1, -1)
        sims = cosine_similarity(cluster_embs, centroid).flatten()
        sims_per_cluster[cluster_id] = (indices, sims)

    paper_sim: dict[str, float] = {}
    for cluster_id, (indices, sims) in sims_per_cluster.items():
        for idx, sim in zip(indices, sims):
            paper_sim[papers[idx]["id"]] = float(sim)

    def sort_key(p):
        cid = p["cluster_id"]
        return (
            cluster_rank.get(cid, 999),
            -paper_sim.get(p["id"], 0.0),
            p.get("published_at", ""),
        )

    return sorted(papers, key=sort_key)
