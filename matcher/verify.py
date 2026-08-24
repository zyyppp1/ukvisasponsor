"""LLM 消歧:用 Claude 核验模糊匹配到的担保方是否真的是招聘方那家公司。

动机(Chalk 案例):字符串匹配把招聘方 "Chalk"(科技公司)错配成 "Chalk Restaurant
Ltd"(餐厅)。纯字面无法区分——区别在上下文(职位是招后端工程师,餐厅显然不是)。
LLM 拿职位上下文能判断,从而否掉误报。这正是"字符串匹配做不到、需要 AI"的地方。

成本控制:精确匹配(method="exact")天然高可信,不核验;只把**模糊**候选交给 LLM。
"""

import os

from pydantic import BaseModel

from .register import Match

# 默认 Opus 5;高并发/追求便宜可设 SPONSOR_VERIFY_MODEL=claude-haiku-4-5
VERIFY_MODEL = os.environ.get("SPONSOR_VERIFY_MODEL", "claude-opus-5")

_SYSTEM = (
    "You verify whether entries in the UK Home Office register of licensed visa sponsors "
    "refer to the SAME real-world organisation that is hiring for a given job. "
    "Be strict and use the job context: a restaurant is not the tech company hiring a "
    "software engineer, even if the names overlap. Only accept an entry if it is plausibly "
    "the same employer. If none of the entries is the hiring company, return an empty list."
)


class _Verdict(BaseModel):
    matched_indexes: list[int]   # 候选列表里"确属招聘方"的下标
    is_licensed_sponsor: bool     # 招聘方看起来是否为持牌担保方
    reason: str                   # 简短理由


def _build_prompt(query, names, job_title, job_description):
    lines = "\n".join(f"{i}: {n}" for i, n in enumerate(names))
    ctx = []
    if job_title:
        ctx.append(f"Job title: {job_title}")
    if job_description:
        ctx.append(f"Job description (excerpt): {job_description[:1500]}")
    context = ("\n".join(ctx)) or "(no extra job context provided)"
    return (
        f"A job listing shows the hiring company as: \"{query}\".\n"
        f"{context}\n\n"
        f"Candidate register entities (licensed sponsors):\n{lines}\n\n"
        "Which candidate indexes, if any, are the SAME organisation as the hiring company? "
        "Return their indexes (empty list if none), whether the hiring company appears to be a "
        "licensed sponsor, and a one-sentence reason."
    )


def disambiguate(query, names, job_title=None, job_description=None, client=None, model=VERIFY_MODEL):
    """问 LLM:候选里哪些确属招聘方那家公司。返回 (matched_indexes, is_sponsor, reason)。

    client 可注入(测试用假 client,免真调 API)。默认懒创建真 client。
    """
    if client is None:
        import anthropic  # 延迟导入:没装/没 key 时不影响其余功能
        client = anthropic.Anthropic()

    resp = client.messages.parse(
        model=model,
        max_tokens=2048,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(query, names, job_title, job_description)}],
        output_format=_Verdict,
    )
    v = resp.parsed_output
    return v.matched_indexes, v.is_licensed_sponsor, v.reason


def verify_matches(query, matches, job_title=None, job_description=None, client=None):
    """精确匹配原样保留;模糊匹配交 LLM 过滤。返回 (filtered_matches, reason)。"""
    exact = [m for m in matches if m.method == "exact"]
    fuzzy = [m for m in matches if m.method == "fuzzy"]
    if not fuzzy:
        return matches, None

    unique_names = list(dict.fromkeys(m.sponsor.name for m in fuzzy))
    idxs, _is_sponsor, reason = disambiguate(query, unique_names, job_title, job_description, client=client)
    kept_names = {unique_names[i] for i in idxs if 0 <= i < len(unique_names)}
    kept_fuzzy = [m for m in fuzzy if m.sponsor.name in kept_names]
    return exact + kept_fuzzy, reason
