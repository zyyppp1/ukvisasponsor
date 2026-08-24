"""从 Postgres 读所有担保方,构建内存里的 SponsorIndex。

设计取舍:我们保留 Phase 1 那个调好的内存匹配器(精确字典 + 模糊),只把**数据来源**
从 CSV 换成数据库。匹配逻辑一行不动 —— API 边界让"数据存哪"和"怎么匹配"互相解耦。
(更"数据库原生"的做法是把匹配下推到 SQL + pg_trgm,属于后续增强。)
"""

from sqlalchemy import select

from db.database import SessionLocal
from db.models import SponsorRow
from matcher.register import Sponsor, SponsorIndex


def load_index_from_db() -> SponsorIndex:
    with SessionLocal() as session:
        rows = session.execute(select(SponsorRow)).scalars().all()
        sponsors = [
            Sponsor(
                name=r.organisation_name,
                town=r.town,
                county=r.county,
                rating=r.rating,
                route=r.route,
            )
            for r in rows
        ]
    return SponsorIndex(sponsors)
