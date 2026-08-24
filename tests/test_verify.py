"""LLM 消歧的过滤逻辑测试。

不真调 Claude —— 注入一个假 client(返回预设裁决),只测"精确保留 + 模糊按裁决过滤"
这段逻辑。真实 LLM 行为要靠带 key 的手动/集成测试。
"""

from matcher.register import Match, Sponsor
from matcher.verify import _Verdict, verify_matches


def sp(name):
    return Sponsor(name=name, town="London", county="", rating="Worker (A rating)", route="Skilled Worker")


class _FakeClient:
    """messages.parse(...) 固定返回预设 _Verdict。"""
    def __init__(self, verdict):
        self.messages = self
        self._verdict = verdict

    def parse(self, **kwargs):
        class _Resp:
            parsed_output = self._verdict
        return _Resp()


def test_fuzzy_false_positives_are_dropped():
    # Chalk 场景:两个餐厅模糊命中,LLM 裁决"都不是"→ 应被过滤光
    matches = [
        Match(sp("Chalk Restaurant Ltd"), 100.0, "fuzzy"),
        Match(sp("Chalk restaurants ltd"), 100.0, "fuzzy"),
    ]
    client = _FakeClient(_Verdict(matched_indexes=[], is_licensed_sponsor=False, reason="restaurants, not the tech employer"))
    kept, reason = verify_matches("Chalk", matches, job_title="Backend Engineer", client=client)
    assert kept == []
    assert "restaurant" in reason.lower()


def test_fuzzy_true_positive_is_kept():
    matches = [Match(sp("Deloitte LLP"), 93.0, "fuzzy")]
    client = _FakeClient(_Verdict(matched_indexes=[0], is_licensed_sponsor=True, reason="same firm"))
    kept, _ = verify_matches("Deloite", matches, client=client)
    assert [m.sponsor.name for m in kept] == ["Deloitte LLP"]


def test_exact_matches_pass_through_without_calling_llm():
    # 全是精确匹配时,不需要也不应该调 LLM;假 client 会因裁决为空而"全滤掉",
    # 但精确匹配不该被送去过滤 —— 用一个会 raise 的 client 证明它没被调用。
    class Boom:
        def __getattr__(self, _):
            raise AssertionError("LLM should not be called for exact matches")
    matches = [Match(sp("Monzo Bank Ltd"), 100.0, "exact")]
    kept, reason = verify_matches("Monzo Bank", matches, client=Boom())
    assert [m.sponsor.name for m in kept] == ["Monzo Bank Ltd"]
    assert reason is None
