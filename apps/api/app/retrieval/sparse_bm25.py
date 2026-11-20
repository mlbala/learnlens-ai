"""Lightweight BM25-like scorer for the in-memory vector store (offline tests).

Not a substitute for Qdrant Cloud `Qdrant/bm25` Document vectors in production;
kept deterministic and dependency-free for CI.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN.finditer(text or "")]


@dataclass(slots=True)
class Bm25Index:
    """Simple BM25 Okapi over an in-memory corpus."""

    k1: float = 1.5
    b: float = 0.75
    doc_tokens: dict[str, list[str]] | None = None
    doc_len: dict[str, int] | None = None
    df: Counter[str] | None = None
    avgdl: float = 0.0
    n_docs: int = 0

    def __post_init__(self) -> None:
        self.doc_tokens = self.doc_tokens or {}
        self.doc_len = self.doc_len or {}
        self.df = self.df or Counter()

    def add(self, doc_id: str, text: str) -> None:
        assert self.doc_tokens is not None and self.doc_len is not None and self.df is not None
        tokens = tokenize(text)
        # Replacing an existing doc: drop old df contributions.
        if doc_id in self.doc_tokens:
            old = set(self.doc_tokens[doc_id])
            for term in old:
                self.df[term] = max(0, self.df[term] - 1)
            self.n_docs -= 1
        self.doc_tokens[doc_id] = tokens
        self.doc_len[doc_id] = len(tokens)
        self.n_docs += 1
        for term in set(tokens):
            self.df[term] += 1
        total = sum(self.doc_len.values()) or 1
        self.avgdl = total / max(1, self.n_docs)

    def remove(self, doc_id: str) -> None:
        assert self.doc_tokens is not None and self.doc_len is not None and self.df is not None
        if doc_id not in self.doc_tokens:
            return
        for term in set(self.doc_tokens[doc_id]):
            self.df[term] = max(0, self.df[term] - 1)
        del self.doc_tokens[doc_id]
        del self.doc_len[doc_id]
        self.n_docs = max(0, self.n_docs - 1)
        total = sum(self.doc_len.values())
        self.avgdl = (total / self.n_docs) if self.n_docs else 0.0

    def score(self, query: str, doc_id: str) -> float:
        assert self.doc_tokens is not None and self.doc_len is not None and self.df is not None
        if doc_id not in self.doc_tokens or self.n_docs == 0:
            return 0.0
        q_terms = tokenize(query)
        if not q_terms:
            return 0.0
        tf = Counter(self.doc_tokens[doc_id])
        dl = self.doc_len[doc_id] or 1
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            df = self.df.get(term, 0) or 0
            idf = math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
            freq = tf[term]
            denom = freq + self.k1 * (1.0 - self.b + self.b * dl / max(self.avgdl, 1e-9))
            score += idf * (freq * (self.k1 + 1.0)) / max(denom, 1e-9)
        return score

    def ranked(self, query: str, candidate_ids: list[str], *, limit: int) -> list[str]:
        scored = [(doc_id, self.score(query, doc_id)) for doc_id in candidate_ids]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [doc_id for doc_id, s in scored if s > 0.0][:limit]
