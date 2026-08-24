"""担保方索引:把官方名单加载进内存,并按归一化名建一张查找表。

匹配的第二步。归一化(normalize)解决了"写法不同"的问题;这一步用一张
字典(哈希表)把"归一化名 -> 记录"建好索引,让查询从"遍历 14 万行"(O(n))
变成"一次哈希直达"(O(1))。
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize_name


@dataclass(frozen=True)
class Sponsor:
    """名单里的一条担保方记录。frozen=True 让它不可变、可哈希,当值更安全。"""
    name: str      # 原始 Organisation Name(展示给用户看的)
    town: str
    county: str
    rating: str    # Type & Rating,如 "Worker (A rating)"
    route: str     # 如 "Skilled Worker"


class SponsorIndex:
    """归一化名 -> 该名下所有记录 的查找表。"""

    def __init__(self, sponsors):
        # 一个归一化名可能对应多条记录:
        #   - 真实重复(Monzo 出现 3 次,不同路线)
        #   - 不同实体归一化后同名
        # 所以值是"记录列表",不是单条。
        self._index: dict[str, list[Sponsor]] = {}
        for s in sponsors:
            key = normalize_name(s.name)
            if not key:
                continue
            self._index.setdefault(key, []).append(s)

    def exact_match(self, query: str) -> list[Sponsor]:
        """把查询归一化,O(1) 查表,返回候选记录列表(查不到返回空列表)。"""
        key = normalize_name(query)
        if not key:
            return []
        return self._index.get(key, [])

    def __len__(self) -> int:
        """索引里的记录总数。"""
        return sum(len(records) for records in self._index.values())

    @property
    def distinct_names(self) -> int:
        """去重后的归一化名个数(字典的键数)。"""
        return len(self._index)

    @classmethod
    def from_csv(cls, path) -> "SponsorIndex":
        """从官方 CSV 构建索引。encoding='utf-8-sig' 处理开头的 BOM。"""
        sponsors: list[Sponsor] = []
        with open(Path(path), newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sponsors.append(
                    Sponsor(
                        name=(row.get("Organisation Name") or "").strip(),
                        town=(row.get("Town/City") or "").strip(),
                        county=(row.get("County") or "").strip(),
                        rating=(row.get("Type & Rating") or "").strip(),
                        route=(row.get("Route") or "").strip(),
                    )
                )
        return cls(sponsors)
