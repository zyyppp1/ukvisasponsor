"""SponsorIndex 精确匹配的单元测试。

用一个小的内存 fixture(而不是真实 10MB CSV)——单元测试要快、要确定,
不该依赖会每天变的外部文件。
"""

import pytest

from matcher.register import Sponsor, SponsorIndex


def make(name, town="London", county="", rating="Worker (A rating)", route="Skilled Worker"):
    return Sponsor(name=name, town=town, county=county, rating=rating, route=route)


@pytest.fixture
def index():
    return SponsorIndex([
        make("Monzo Bank Ltd", route="Skilled Worker"),
        make("Monzo Bank Limited", route="Temporary Worker (A rating)"),  # 归一化后同名
        make("Google (UK) Limited"),
        make("Amazon UK Services Ltd", town="London"),
        make("Amazon Filters Ltd", town="Redditch"),  # 同以 amazon 开头,但归一化名不同
    ])


def test_exact_match_found(index):
    # 完整名字(归一化后 == "monzo bank")才命中,两条记录都返回
    results = index.exact_match("Monzo Bank")
    assert len(results) == 2                      # 两条都归一成 "monzo bank"
    assert {r.name for r in results} == {"Monzo Bank Ltd", "Monzo Bank Limited"}


def test_exact_match_is_all_or_nothing(index):
    # 精确匹配的本质局限:少打一个词就对不上。
    # "Monzo" 归一成 "monzo" != "monzo bank" —— 这正是模糊匹配要解决的。
    assert index.exact_match("Monzo") == []


def test_exact_match_is_case_and_suffix_insensitive(index):
    # 查询本身也走同一个 normalize,所以大小写/空格/后缀都不影响
    assert len(index.exact_match("  MONZO bank LIMITED ")) == 2


def test_bracketed_name_matches(index):
    results = index.exact_match("Google")
    assert len(results) == 1
    assert results[0].name == "Google (UK) Limited"


def test_no_match_returns_empty_list(index):
    assert index.exact_match("Definitely Not A Sponsor") == []


def test_amazon_variants_are_separate_keys(index):
    # 'Amazon UK Services' 和 'Amazon Filters' 归一化名不同,精确匹配不会混在一起
    assert len(index.exact_match("Amazon UK Services")) == 1
    assert len(index.exact_match("Amazon Filters")) == 1
    # 用户只输入 "Amazon" 时,精确匹配一个都对不上 —— 正是模糊匹配要解决的
    assert index.exact_match("Amazon") == []


def test_len_and_distinct_names(index):
    assert len(index) == 5          # 5 条记录
    assert index.distinct_names == 4  # monzo bank / google / amazon services / amazon filters
