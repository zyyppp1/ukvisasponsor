"""HTTP API:把匹配器暴露成一个别人能通过网址调用的 Web 服务。

关键设计:索引在服务器**启动时建一次**(lifespan),常驻内存;之后每个请求
复用它。这就是对"每次都重建吗?"的答案——不,建一次,服务无数次请求。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from matcher.register import Match, SponsorIndex
from matcher.verify import verify_matches

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sponsors.csv"

# 常驻内存的索引。None 表示还没建好。
_index: SponsorIndex | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器生命周期钩子:启动时建索引(一次,O(n)),关闭时释放。"""
    global _index
    _index = SponsorIndex.from_csv(DATA_PATH)
    yield          # yield 之前 = 启动;之后 = 关闭
    _index = None


app = FastAPI(
    title="UK Visa Sponsor Checker API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS:浏览器默认禁止网页/扩展调用"别的源"的接口(安全机制)。这里放行,
# 让 Chrome 扩展能调本 API。开发期用 "*" 全放行;上线应收紧到具体来源。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_index() -> SponsorIndex:
    """依赖注入:给端点提供常驻索引;还没建好就回 503(服务未就绪)。

    单独抽成函数,测试里可以用 app.dependency_overrides 换成小索引,不必加载 14 万行。
    """
    if _index is None:
        raise HTTPException(status_code=503, detail="Index not ready")
    return _index


# ---- 响应模型:声明 API 返回的 JSON 结构 ----
# FastAPI 用它做两件事:① 自动把返回值序列化成 JSON;② 生成 /docs 交互文档。
class SponsorOut(BaseModel):
    name: str
    town: str
    county: str
    rating: str
    route: str


class MatchOut(BaseModel):
    sponsor: SponsorOut
    score: float
    method: str          # "exact" 或 "fuzzy"


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[MatchOut]
    verified: bool = False                 # 是否经过 LLM 核验
    verification_reason: str | None = None  # LLM 的一句话理由(或跳过原因)


def _to_match_out(m: Match) -> MatchOut:
    s = m.sponsor
    return MatchOut(
        sponsor=SponsorOut(name=s.name, town=s.town, county=s.county, rating=s.rating, route=s.route),
        score=m.score,
        method=m.method,
    )


@app.get("/health")
def health(index: SponsorIndex = Depends(get_index)):
    """健康检查:确认索引已加载,顺便报出规模。"""
    return {"status": "ok", "records": len(index), "distinct_names": index.distinct_names}


@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="职位页上看到的公司名"),
    limit: int = Query(5, ge=1, le=25, description="最多返回几个候选"),
    title: str | None = Query(None, description="职位标题(给 LLM 消歧当上下文)"),
    description: str | None = Query(None, description="职位描述节选(上下文)"),
    verify: bool = Query(False, description="是否用 LLM 核验模糊匹配(需 ANTHROPIC_API_KEY)"),
    index: SponsorIndex = Depends(get_index),
):
    """查一个公司名 -> 返回候选担保方(带分数和匹配方式)。

    用 GET:这是一次"只读查询",没有副作用、可重复、可缓存,符合 REST 惯例。
    q 是必填查询参数(?q=Amazon);缺了 FastAPI 会自动回 422。
    verify=true 时,对模糊匹配用 LLM 结合职位上下文消歧(治 Chalk 那种误报)。
    """
    matches = index.search(q, limit=limit)
    verified = False
    reason = None
    if verify and matches:
        try:
            matches, reason = verify_matches(q, matches, title, description)
            verified = True
        except Exception as exc:
            # 无 key / LLM 出错:退回未核验结果(fail-open),不让整个查询挂掉
            reason = f"verification skipped: {exc.__class__.__name__}"
    return SearchResponse(
        query=q,
        count=len(matches),
        results=[_to_match_out(m) for m in matches],
        verified=verified,
        verification_reason=reason,
    )
