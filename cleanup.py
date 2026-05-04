"""One-off: trim articles to the intended 90-day window and drop bad timestamps."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from db import get_conn

# 90-day window (matches our ingest config; +5 day buffer)
cutoff = (datetime.now(timezone.utc) - timedelta(days=95)).date().isoformat()

with get_conn() as conn:
    n_before = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    n_bad = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE published < ?", (cutoff,)
    ).fetchone()[0]
    conn.execute("DELETE FROM articles WHERE published < ?", (cutoff,))
    conn.execute("VACUUM")
    n_after = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

print(f"Cutoff: {cutoff}")
print(f"Before: {n_before:,}")
print(f"Trimmed: {n_bad:,}")
print(f"After: {n_after:,}")