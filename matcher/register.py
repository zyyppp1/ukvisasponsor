"""担保方索引:把官方名单加载进内存,并按归一化名建一张查找表。

匹配的第二步。归一化(normalize)解决了"写法不同"的问题;这一步用一张
字典(哈希表)把"归一化名 -> 记录"建好索引,让查询从"遍历 14 万行"(O(n))
变成"一次哈希直达"(O(1))。
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

from .normalize import normalize_name


@dataclass(frozen=True)
class Sponsor:
    """名单里的一条担保方记录。frozen=True 让它不可变、可哈希,当值更安全。"""
    name: str      # 原始 Organisation Name(展示给用户看的)
    town: str
    county: str
    rating: str    # Type & Rating,如 "Worker (A rating)"
    route: str     # 如 "Skilled Worker"


@dataclass
class Match:
    """一条匹配结果:命中的记录 + 相似度分数 + 用了哪种方法。"""
    sponsor: Sponsor
    score: float          # 0-100,精确命中记 100
    method: str           # "exact" 或 "fuzzy"


def _query_token_coverage(query_key: str, candidate_key: str, token_threshold: float = 80) -> float:
    """查询里有多大比例的词能在候选名里找到(词级比对,容忍拼写误差)。

    模糊匹配的"准确率闸门"。token_set_ratio 只要共享一个词就可能给高分
    (如 "j p morgan" 误配 "morgan lewis"),这里要求查询的大部分词都真的出现在
    候选里,把"只蹭了一个词"的无关公司挡掉。
    """
    q_tokens = query_key.split()
    c_tokens = candidate_key.split()
    if not q_tokens:
        return 0.0
    hits = sum(
        1 for qt in q_tokens
        if any(qt == ct or fuzz.ratio(qt, ct) >= token_threshold for ct in c_tokens)
    )
    return hits / len(q_tokens)


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
        # 去重后的归一化名列表,供模糊匹配扫描(建一次,反复用)
        self._keys: list[str] = list(self._index.keys())

    def exact_match(self, query: str) -> list[Sponsor]:
        """把查询归一化,O(1) 查表,返回候选记录列表(查不到返回空列表)。"""
        key = normalize_name(query)
        if not key:
            return []
        return self._index.get(key, [])

    def search(
        self,
        query: str,
        limit: int = 5,
        score_cutoff: float = 85,
        coverage_cutoff: float = 0.7,
    ) -> list[Match]:
        """匹配入口:先走 O(1) 精确;精确没命中再"宽召回 + 准确率闸门"模糊兜底。

        - 精确命中:返回该名下所有记录,score=100,method="exact"。
        - 模糊兜底:两步——
            1) token_set_ratio 宽松捞出一批候选(保召回,容忍多词/少词/拼写错误);
            2) 用查询词覆盖率闸门(_query_token_coverage)过滤掉"只蹭一个词"的
               无关公司(保准确)。
          单一打分器无法兼顾:token_set 太松(误配 morgan lewis)、token_sort/ratio
          太严(漏掉 "Amazon" 这类少词查询)。组合两者才平衡。

        两个旋钮:score_cutoff(token_set 的分数门槛)和 coverage_cutoff(查询词
        需被覆盖的比例)——都是"准确率 vs 召回率"的权衡,没有完美值,是业务取舍。
        已知局限:极端字母换位的拼写错误(如 Wies→Wise,仅 75 分)会漏;个别近形词
        (如 Onzo↔Monzo)会以低排名混入。彻底解决要靠语义匹配(embeddings,阶段 6)。
        """
        key = normalize_name(query)
        if not key:
            return []

        # 快路径:精确匹配(O(1))
        exact = self._index.get(key)
        if exact:
            return [Match(s, 100.0, "exact") for s in exact]

        # 慢路径:模糊兜底(在 self._keys 上扫描,O(n) per query)
        # 先多捞一些(limit*4),再经覆盖率闸门过滤,免得过滤后不够数。
        raw = process.extract(
            key,
            self._keys,
            scorer=fuzz.token_set_ratio,
            limit=limit * 4,
            score_cutoff=score_cutoff,
        )
        results: list[Match] = []
        for matched_key, score, _ in raw:
            if _query_token_coverage(key, matched_key) < coverage_cutoff:
                continue
            for s in self._index[matched_key]:
                results.append(Match(s, float(score), "fuzzy"))
            if len(results) >= limit:
                break
        return results

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
