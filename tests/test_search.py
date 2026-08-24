"""SponsorIndex.search 的单元测试:精确快路径 + 模糊兜底 + 准确率闸门。

用小 fixture,断言"方法/是否命中/关键候选在不在",不硬编码具体分数(分数脆弱)。
"""

import pytest

from matcher.register import Sponsor, SponsorIndex


def make(name, town="London"):
    return Sponsor(name=name, town=town, county="", rating="Worker (A rating)", route="Skilled Worker")


@pytest.fixture
def index():
    return SponsorIndex([
        make("Amazon UK Services Ltd"),
        make("Amazon Filters Ltd", town="Camberley"),
        make("Monzo Bank Ltd"),
        make("Deloitte LLP"),
        make("Morgan Lewis & Bockius UK LLP"),  # 验证不会被 "J P Morgan" 误配
        make("Wise Payments Limited"),
    ])


def test_exact_takes_fast_path(index):
    results = index.search("Monzo Bank")
    assert results[0].method == "exact"
    assert results[0].score == 100.0
    assert results[0].sponsor.name == "Monzo Bank Ltd"


def test_fuzzy_recalls_missing_word_query(index):
    # 用户只打 "Amazon" —— 精确对不上,模糊应捞出两个 Amazon 实体
    results = index.search("Amazon")
    names = {m.sponsor.name for m in results}
    assert {"Amazon UK Services Ltd", "Amazon Filters Ltd"} <= names
    assert all(m.method == "fuzzy" for m in results)


def test_coverage_guard_blocks_shared_single_token(index):
    # "J P Morgan" 只和 "Morgan Lewis..." 共享一个词(morgan),覆盖率 1/3 < 0.7,应被挡掉
    results = index.search("J P Morgan")
    assert "Morgan Lewis & Bockius UK LLP" not in {m.sponsor.name for m in results}


def test_fuzzy_tolerates_typo(index):
    # "Deloite" 少一个 t,ratio~93,应命中 Deloitte
    results = index.search("Deloite")
    assert any(m.sponsor.name == "Deloitte LLP" for m in results)


def test_no_match_returns_empty(index):
    assert index.search("Totally Unrelated Xyz Corp") == []


def test_empty_query_returns_empty(index):
    assert index.search("") == []
