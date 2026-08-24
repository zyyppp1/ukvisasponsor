"""API 层的测试:用 FastAPI 的 TestClient 发真实的 HTTP 请求(不用真开端口)。

用 dependency_overrides 把索引换成一个小的内存索引,这样测试:
  - 快(不加载 14 万行);
  - 确定(不依赖每天变的 CSV)。
"""

from fastapi.testclient import TestClient

from app.main import app, get_index
from matcher.register import Sponsor, SponsorIndex


def _tiny_index():
    return SponsorIndex([
        Sponsor("Monzo Bank Ltd", "London", "", "Worker (A rating)", "Skilled Worker"),
        Sponsor("Amazon UK Services Ltd", "London", "", "Worker (A rating)", "Skilled Worker"),
        Sponsor("Amazon Filters Ltd", "Camberley", "", "Worker (A rating)", "Skilled Worker"),
    ])


# 把端点依赖的 get_index 换成小索引
app.dependency_overrides[get_index] = _tiny_index
client = TestClient(app)


def test_search_exact_returns_200_and_json():
    resp = client.get("/search", params={"q": "Monzo Bank"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Monzo Bank"
    assert data["results"][0]["method"] == "exact"
    assert data["results"][0]["sponsor"]["name"] == "Monzo Bank Ltd"


def test_search_fuzzy_recalls_candidates():
    resp = client.get("/search", params={"q": "Amazon"})
    assert resp.status_code == 200
    names = {m["sponsor"]["name"] for m in resp.json()["results"]}
    assert "Amazon UK Services Ltd" in names
    assert "Amazon Filters Ltd" in names


def test_missing_query_param_is_422():
    # q 是必填的,缺了 FastAPI 自动返回 422(校验错误)——不用我们手写检查
    resp = client.get("/search")
    assert resp.status_code == 422


def test_limit_out_of_range_is_422():
    resp = client.get("/search", params={"q": "Amazon", "limit": 999})
    assert resp.status_code == 422


def test_health_reports_index_size():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["records"] == 3
