from db import get_conn

with get_conn() as conn:
    n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    sample = conn.execute(
        "SELECT ticker, published, headline FROM articles "
        "ORDER BY published DESC LIMIT 5"
    ).fetchall()

print(f"Total articles: {n}")
print("\nMost recent 5:")
for ticker, pub, headline in sample:
    print(f"  [{ticker}] {pub:%Y-%m-%d %H:%M}  {headline[:80]}")