# UK Visa Sponsor Checker — 开发笔记

## 阶段 0:数据获取与剖析(2026-08-24)

### 数据源
- 英国内政部《Register of licensed sponsors: workers》,GOV.UK 公开数据,每个工作日更新。
- 页面:https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers
- 当日 CSV 直链每天变(带日期),下载脚本需先解析发布页拿到当天链接。
- 免费、公开、无需授权。面试话术:"数据直接来自官方,不爬不猜。"

### 文件规模
- 142,908 行数据,~10.4 MB。

### 字段(5 列)
| 列 | 含义 | 用途 |
|---|---|---|
| Organisation Name | 担保方法定名称 | **匹配的目标**(核心) |
| Town/City | 城市 | 消歧(多家同名时) |
| County | 郡 | 消歧 |
| Type & Rating | 类型+评级,如 "Worker (A rating)" | 显示可信度;99% 是 A rating |
| Route | 签证路线,如 "Skilled Worker" | 过滤;86% 是 Skilled Worker |

### 核心难点:名称匹配的真实失败案例
- **J.P. Morgan → 0 条**:名单里没有带点的写法,朴素子串搜索直接漏掉一个大雇主。
- **Revolut → 15 条子串命中**,但只有 'Revolut Ltd' 是那家金融公司,其余全是 "Revolution ..." 的误命中。
- **Amazon → 8 条**:混入 Amazon Filters、Amazonico(餐厅)、"The Amazon" 等无关公司。
- **Monzo → 'Monzo Bank Ltd' 重复出现 3 次**:同一公司多行(多路线/实体)。
- **Google → 'Google (UK) Limited'**:含括号。

### 数据有多脏(必须归一化的证据)
- 5.3%(7,643 条)名字带前后多余空格。
- 34,985 条全大写。
- 后缀写法不统一:LTD 61,457 条 / LIMITED 52,923 条 / PLC 834 / LLP 1,979。
- 归一化后完全重名:13,856 组(如 'subway' 7 次)。

### 结论(引出阶段 1)
匹配不能用"子串包含"。需要:①归一化(去空格/大小写/法律后缀)②精确匹配优先 ③模糊匹配兜底 ④返回多个候选而非硬选一个 ⑤用城市消歧。
两种失败方向要分清:**漏匹配(该找到没找到=召回率低)** vs **误匹配(找错=准确率低)**。

### 面试可能被问(阶段 0)
- Q: 数据从哪来,可靠吗? → 官方每日更新的公开名单。
- Q: 为什么不能直接按逗号切 CSV? → 字段内可能含逗号,必须用带引号处理的 CSV 解析器。
- Q: 数据多大,怎么存? → 14 万行,阶段 1 先放内存,阶段 3 进 Postgres。

## 阶段 1:匹配器(纯 Python + 测试)

### 1a 归一化(matcher/normalize.py)
把写法各异的公司名压成统一形式:去重音→小写→&转and→丢括号/逗号后内容→去标点→去法律后缀噪声词(ltd/plc/llp/uk...)→全噪声兜底。目的:让"本该相等"的名字真的字节相等。8 个测试,用例全来自阶段 0 的真实脏数据。

### 1b 精确匹配 + 字典索引(matcher/register.py)
- `Sponsor` frozen dataclass 表一条记录;`SponsorIndex` 按"归一化名 → 记录列表"建字典。
- 值是列表:同名多记录(重复 + 多实体)全保留,返回候选而非硬选。
- 复杂度:建索引 O(n) 一次(14 万行 0.9s),之后每次查 O(1)(实测 2-16 微秒)。
- 真实数据:142,905 条 → 125,874 个去重归一名(归一化合并了约 1.7 万写法变体)。
- **意外收获**:精确匹配天然消除了阶段 0 的 Revolut→"Revolution..." 误命中(准确率提升,零额外代码)。
- **局限**:全等匹配对"多词/少词"无能为力——"Amazon"(太少词)和"J.P. Morgan"(名单里多了 Securities)仍 0 命中 → 召回率问题 → 引出 1c 模糊匹配。

### 1c 模糊匹配(matcher/register.py: search)
精确对不上时的兜底。经过真实数据横评得出的关键结论:**单一打分器无法兼顾准确率和召回率**。
- token_set_ratio:召回高,但只共享一个词就冲高分(j p morgan 误配 morgan lewis)→ 准确率差。
- WRatio:换一种垃圾——字符子串误配(amazon→AZO、deloite→ITE)。
- token_sort_ratio/ratio:准确率高,但漏掉"少词查询"(Amazon 返回空)。
**最终方案(组合):token_set_ratio 宽召回 + 查询词覆盖率闸门(词级阈值80、覆盖0.7)保准确。**
- 效果:Google/Revolut 走精确(0ms,且天然无 Revolution 误配);Amazon→3 个 Amazon 实体、Barclays→3 个 Barclays 实体(模糊,~60ms);Deloite 拼写错误→Deloitte;J.P. Morgan→0(正确,该行本就没持牌)。
- 性能:精确 O(1) 0ms;模糊 O(n) 扫 12 万键 ~60ms → 所以"精确优先、模糊兜底"。模糊要扩展得靠 trigram 索引/分块(阶段 3 Postgres)。
- 已知局限(诚实记录):极端换位拼写(Wies→Wise 仅75分)会漏;个别近形词(Onzo↔Monzo)低排名混入 → 彻底解决靠语义匹配 embeddings(阶段 6)。
- score/coverage 两个旋钮 = 准确率 vs 召回率的业务权衡,无完美值。

### 数据处理进度(诚实盘点)
磁盘上 CSV 仍是原始未改动;所有处理都是运行时内存里做的(字段 strip + 公司名归一化建键),未落盘、未入库。管道坐标:抽取✅ / 转换🟡(仅内存、仅公司名)/ 校验·去重落盘·入库⬜。真正 ETL 在阶段 3 + DE 层。

### 面试串词
归一化 + 精确匹配 = 高准确率、低召回率;模糊匹配用"牺牲一点准确率换召回率"来补;两者叠加 = 完整匹配器。字典 O(1) vs 遍历 O(n);建一次查多次(build once, serve many);数据日更靠重启重建或热刷新,阶段 3 入库后变持久化索引 + 增量维护。

## 阶段 2:HTTP API(app/main.py)

- FastAPI + uvicorn。索引在 lifespan **启动时建一次**、常驻内存(/health 显示 142905 条即证据)。
- 端点:`GET /search?q=&limit=`(只读查询用 GET)、`GET /health`。
- Pydantic 响应模型(SponsorOut/MatchOut/SearchResponse)→ 自动序列化 JSON + 自动生成 /docs 交互文档。
- 依赖注入 get_index + Depends → 测试用 dependency_overrides 换成小索引(快、稳,不加载 14 万行)。
- 真实 curl 验证:/health 200、/search 返 JSON、缺 q 自动 422、/docs 200。测试新增 test_api.py(TestClient),共 26 个全绿。
- 概念:HTTP 请求/响应、GET vs POST、状态码(200/422/503)、查询参数、JSON;API/端点/REST 解耦后端与调用方;FastAPI 把函数变端点 + 自动校验 + 自动文档。
- 待打磨(留后面):① limit 现按"记录条数"算,同公司多路线(如 Amazon UK Services 有 3 行 = 3 条路线)会占名额 → 应按公司去重、聚合路线;② 分数四舍五入。
- 面试题:HTTP/REST 是什么、GET vs POST、为何启动时建索引、如何测 API(TestClient + 依赖替换)、422/503 含义。
