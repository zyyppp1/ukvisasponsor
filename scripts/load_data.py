"""ETL:把官方 CSV 清洗后批量灌进 Postgres 的 sponsors 表。

三个数据工程要点(代码里对应标注):
- 幂等(idempotent):先 TRUNCATE 清空再灌 → 脚本重复跑不会灌出重复数据。
- 批量插入(bulk insert):一次插一批(而不是一行一次网络往返)→ 快几十倍。
- 事务(transaction):整批要么全进、要么全回滚 → 不会留下"灌了一半"的坏状态。

    python scripts/load_data.py
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import insert, text

from db.database import SessionLocal, engine
from db.models import Base, SponsorRow
from matcher.normalize import normalize_name

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "sponsors.csv"
CHUNK = 10000


def rows_from_csv(path):
    """读 CSV、清洗(strip)、算归一化名,产出一行行 dict。归一化为空的跳过。"""
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = (r.get("Organisation Name") or "").strip()
            norm = normalize_name(name)
            if not norm:
                continue
            yield {
                "organisation_name": name,
                "normalized_name": norm,
                "town": (r.get("Town/City") or "").strip(),
                "county": (r.get("County") or "").strip(),
                "rating": (r.get("Type & Rating") or "").strip(),
                "route": (r.get("Route") or "").strip(),
            }


def load(path=CSV_PATH):
    Base.metadata.create_all(engine)          # 确保表在
    rows = list(rows_from_csv(path))
    t0 = time.perf_counter()
    with SessionLocal() as session:           # 一个 session = 一个事务边界
        # 幂等:先清空(RESTART IDENTITY 让自增 id 也归零)
        session.execute(text("TRUNCATE TABLE sponsors RESTART IDENTITY"))
        # 批量插入:每 CHUNK 行一批
        for i in range(0, len(rows), CHUNK):
            session.execute(insert(SponsorRow), rows[i:i + CHUNK])
        session.commit()                      # 提交:到这一刻整批才真正落库(事务)
    return len(rows), (time.perf_counter() - t0) * 1000


if __name__ == "__main__":
    n, ms = load()
    print(f"已灌入 {n:,} 行,耗时 {ms:.0f} ms")
