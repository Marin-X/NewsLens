"""FinBERT sentiment scoring for ingested articles."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import torch
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from db import get_conn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sentiment")

# Quiet HF/transformers/httpx noise
for _name in ("httpx", "huggingface_hub", "transformers", "urllib3"):
    logging.getLogger(_name).setLevel(logging.WARNING)

MODEL_NAME = "ProsusAI/finbert"
MAX_LENGTH = 256       # headline + summary fits comfortably
BATCH_SIZE = 32
LABELS = ["positive", "negative", "neutral"]  # FinBERT label order


class FinBERT:
    """Thin wrapper around ProsusAI/finbert for batched inference."""

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        log.info("Loading %s on %s", MODEL_NAME, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()

        # Confirm label order matches FinBERT's config
        id2label = self.model.config.id2label
        self._label_order = [id2label[i].lower() for i in range(len(id2label))]
        log.info("Model labels (id->label): %s", id2label)

    @torch.inference_mode()
    def score_batch(self, texts: list[str]) -> list[dict]:
        """Return per-text dict with label, prob_positive, prob_neutral, prob_negative, compound."""
        enc = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        ).to(self.device)
        logits = self.model(**enc).logits
        probs = torch.softmax(logits, dim=-1).cpu().numpy()

        out = []
        for row in probs:
            scores = {label: float(row[i]) for i, label in enumerate(self._label_order)}
            pos = scores.get("positive", 0.0)
            neg = scores.get("negative", 0.0)
            neu = scores.get("neutral", 0.0)
            top = max(scores, key=scores.get)
            out.append(
                {
                    "label": top,
                    "score_pos": pos,
                    "score_neu": neu,
                    "score_neg": neg,
                    "compound": pos - neg,  # signed score in [-1, 1]
                }
            )
        return out


def _make_text(headline: str, summary: str | None) -> str:
    """Concatenate headline + summary; FinBERT trained on short finance snippets."""
    if summary and summary.strip() and summary.strip() != headline.strip():
        return f"{headline}. {summary}"
    return headline


def score_unscored(batch_size: int = BATCH_SIZE, limit: int | None = None) -> dict:
    """Score every article without an existing sentiment row."""
    finbert = FinBERT()

    with get_conn() as conn:
        query = """
            SELECT a.id, a.headline, a.summary
            FROM articles a
            LEFT JOIN sentiment s ON s.article_id = a.id
            WHERE s.article_id IS NULL
            ORDER BY a.id
        """
        if limit:
            query += f" LIMIT {int(limit)}"
        rows = conn.execute(query).fetchall()

    if not rows:
        log.info("Nothing to score.")
        return {"scored": 0}

    log.info("Scoring %d articles in batches of %d", len(rows), batch_size)
    now = datetime.now(timezone.utc)
    inserted = 0

    with get_conn() as conn:
        for start in tqdm(range(0, len(rows), batch_size), desc="Batches"):
            chunk = rows[start : start + batch_size]
            texts = [_make_text(h, s) for _, h, s in chunk]
            results = finbert.score_batch(texts)

            payload = [
                (
                    article_id,
                    r["label"],
                    r["score_pos"],
                    r["score_neu"],
                    r["score_neg"],
                    r["compound"],
                    now,
                )
                for (article_id, _, _), r in zip(chunk, results)
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO sentiment
                    (article_id, label, score_pos, score_neu, score_neg, compound, scored_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            inserted += len(payload)

    log.info("Done. Scored %d articles.", inserted)
    return {"scored": inserted}


if __name__ == "__main__":
    # Score everything
    result = score_unscored()
    print("\nResult:", result)

    # Sample distribution
    with get_conn() as conn:
        dist = conn.execute(
            "SELECT label, COUNT(*) FROM sentiment GROUP BY label ORDER BY 2 DESC"
        ).fetchall()
        sample = conn.execute(
            """
            SELECT a.ticker, s.label, s.compound, a.headline
            FROM sentiment s
            JOIN articles a ON a.id = s.article_id
            ORDER BY s.scored_at DESC, s.compound DESC
            LIMIT 8
            """
        ).fetchall()

    print("\nLabel distribution so far:")
    for label, n in dist:
        print(f"  {label:10s}  {n}")

    print("\nSample scored articles:")
    for ticker, label, compound, headline in sample:
        print(f"  [{ticker:6s}] {label:9s} {compound:+.3f}  {headline[:70]}")