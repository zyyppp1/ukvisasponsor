"""演示 LLM 消歧:对比"核验前 vs 核验后"的候选。

需要 ANTHROPIC_API_KEY(或已登录的 anthropic profile)。

用法:
    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/verify_demo.py "Chalk" "Backend Engineer"
    # 换便宜快的模型:
    SPONSOR_VERIFY_MODEL=claude-haiku-4-5 python scripts/verify_demo.py "Chalk" "Backend Engineer"
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from matcher.register import SponsorIndex
from matcher.verify import verify_matches


def show(title, matches):
    print(f"\n{title} ({len(matches)}):")
    seen = set()
    for m in matches:
        if m.sponsor.name in seen:
            continue
        seen.add(m.sponsor.name)
        print(f"  {m.score:5.1f} {m.method:5} {m.sponsor.name}  [{m.sponsor.town}]")
    if not matches:
        print("  (none)")


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Chalk"
    job_title = sys.argv[2] if len(sys.argv) > 2 else "Backend Engineer"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("需要 ANTHROPIC_API_KEY。请先:export ANTHROPIC_API_KEY=sk-ant-...")
        return 1

    print(f"查询公司名:{query!r}   职位上下文:{job_title!r}")
    idx = SponsorIndex.from_csv(Path(__file__).resolve().parent.parent / "data" / "sponsors.csv")
    raw = idx.search(query, limit=5)
    show("核验前(纯字符串匹配)", raw)

    verified, reason = verify_matches(query, raw, job_title=job_title)
    show("核验后(LLM + 职位上下文)", verified)
    print(f"\nLLM 理由:{reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
