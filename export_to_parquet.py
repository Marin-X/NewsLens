"""Export articles + sentiment from SQLite to parquet for cloud deploy."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from db import get_conn  # noqa: E402

OUT = ROOT / "data" / "articles.parquet"

with get_conn() as conn:
    df = pd.read_sql_query(
        """
        SELECT a.id, a.ticker, a.headline, a.summary, a.source, a.url,
               a.published, s.label, s.compound,
               s.score_pos, s.score_neu, s.score_neg
        FROM articles a
        JOIN sentiment s ON s.article_id = a.id
        """,
        conn,
        parse_dates=["published"],
    )

print(f"Rows: {len(df):,}")
print(f"Columns: {list(df.columns)}")

df.to_parquet(OUT, index=False, compression="snappy")
size_mb = OUT.stat().st_size / 1024 / 1024
print(f"Saved -> {OUT}")
print(f"Size: {size_mb:.1f} MB")