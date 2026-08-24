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

## 阶段 4a:最小 Chrome 扩展 —— 弹窗调 API(extension/)

- MV3。三个文件:manifest.json(ID+权限声明)、popup.html(弹窗 UI)、popup.js(fetch 调 API + 渲染)。
- 只申请 host_permissions: http://127.0.0.1:8137/*(最小权限,对比原版注入所有站点)。
- API 加了 CORSMiddleware:浏览器默认禁跨源,服务端返回 access-control-allow-origin 才放行(curl 验证 `*` 已返回)。
- 概念:扩展结构(manifest/popup/content script/service worker)、DOM(document.getElementById/createElement)、前端 HTTP(fetch + async/await,相当于 Python 的 requests)、CORS(同源策略 + 服务端 opt-in)。
- 注意:popup 是扩展页,靠 host_permissions 可绕过 CORS;4b 的 content script 跑在 LinkedIn 页面上下文里,受 CORS 约束 → 所以现在给 API 加 CORS 是为 4b 铺路;最规范的做法是网络请求走 background service worker(不受页面 CORS 限制)。
- 无法在本机自动验证浏览器端 → 用户手动 Load unpacked 测试。
- 面试题:扩展有哪几部分、什么是 DOM、前端怎么发 HTTP、CORS 是什么为何存在、最小权限原则。

## 阶段 4b:content script 自动抓取 LinkedIn(extension/content.js + background.js)

真实页面上从"没反应"到跑通的完整调试过程(极好的面试故事):

**问题 1:class 选择器全失效。** LinkedIn 语义搜索页(/jobs/search-results/?currentJobId=)的 class 是**随机哈希**(fed23a02 这种),我原来那套 `.jobs-unified-top-card__company-name` 一个都命不中。
- **定位手段**:用 AppleScript 驱动本机 Chrome,在真实标签页里执行 JS 抓 DOM(比让用户手动 Inspect 高效)。
- **修法**:不靠会变的 class,改靠**稳定结构** —— 取第一个文字干净的 `a[href*="/company/"]` 链接(isCleanCompany 过滤掉 followers/Show/大数字)。实测正确取到 "Hunter Bond"。

**问题 2:fetch 被 CSP 拦(Failed to fetch)。** API 明明在跑,但从页面发请求失败。
- **原因**:我用 AppleScript 注入的 fetch 跑在**页面主世界**,受 LinkedIn 的 **CSP(connect-src)** 约束,不许连 127.0.0.1。
- **关键认知**:content script 跑在**隔离世界**,其 fetch 不受页面 CSP 约束;但为彻底稳妥(CSP + CORS 都绕开),把网络请求交给 **background service worker**(靠 host_permissions,独立于页面)。这才是 MV3 里"从扩展发跨源请求"的规范位置。

**最终架构**:content.js(检测 + 注入徽章 + sendMessage)→ background.js(fetch API)→ 回传渲染。
- SPA 兜底:setInterval 每 1.5s 重检测,公司名变了才重查。
- 结果:真实 LinkedIn 页验证通过 —— "Hunter Bond" → 精确命中 "HUNTER BOND LIMITED"(归一化端到端生效)。

- 局限:搜索页取"第一个干净 /company/ 链接",极少数情况可能取到列表项而非选中职位;徽章是浮层(比原版逐卡片内联简单)。
- 面试题:content script vs 页面脚本(隔离世界)、为什么网络走 background(绕 CSP/CORS)、站点用随机 class 怎么抓(靠结构不靠 class)、SPA 不刷新怎么办、怎么在真实页面上调试(注入 JS 抓 DOM)。

## 阶段 6:LLM 消歧(matcher/verify.py + /search?verify=true)

治的病:字符串匹配把招聘方 "Chalk"(科技公司)错配成 "Chalk Restaurant Ltd"(餐厅)。纯字面无法区分,区别在**上下文**——这正是"字符串做不到、需要 AI"之处。
- 做法:精确匹配天然高可信、**不核验**;只把**模糊**候选 + 职位标题/描述丢给 Claude,让它判断"哪个候选真是招聘方那家公司,或都不是"。省钱、只在有风险时调。
- SDK:`client.messages.parse(..., output_format=Pydantic模型)` → `response.parsed_output`(结构化输出,保证合法 JSON)。默认模型 claude-opus-5;可 SPONSOR_VERIFY_MODEL=claude-haiku-4-5 换便宜快的。
- API:`/search?verify=true&title=...&description=...`;LLM 出错/无 key 时 fail-open 退回未核验结果,不拖垮查询。响应加 verified / verification_reason。
- 测试:注入假 client 测过滤逻辑(精确保留、模糊按裁决过滤),不真调 API、不花钱(3 个测试)。真实行为靠带 key 的 scripts/verify_demo.py。
- 概念:LLM API 调用(prompt→结构化输出)、结构化输出(Pydantic schema 保证 JSON)、"传统方法先跑、LLM 只当重排/核验"的成熟架构、key 管理(env 或 profile,不硬编码)、成本/延迟权衡(精确不调、只核验模糊、可选 Haiku)。
- 面试题:字符串匹配为何治不了 Chalk(上下文缺失)、为什么只核验模糊不核验精确(成本)、结构化输出怎么保证 JSON、key 怎么管、模型怎么选(Opus vs Haiku)。
- 待接:扩展 content script 目前只传公司名;要让浏览器里也享受消歧,需再抓职位标题/描述并 verify=true(后续)。

## 阶段 3:Postgres 持久化(db/ + scripts/)

### 环境:本地 Docker Postgres
`docker run --name uvsc-pg -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=ukvisasponsor -p 5433:5432 -v uvsc-pgdata:/var/lib/postgresql/data -d postgres:16`
连接串:postgresql+psycopg://postgres:devpass@localhost:5433/ukvisasponsor。镜像/容器/数据卷三层:删容器不丢数据(卷独立)。

### 第1步 建表(db/models.py, db/database.py)
- SQLAlchemy ORM:Python 类 SponsorRow ↔ 表 sponsors;create_all 生成 CREATE TABLE。ORM = Python↔SQL 翻译器,防注入(参数化查询)、连接池、跨库。
- normalized_name 建 btree 索引(= 内存字典的持久化版)。

### 第2步 ETL 灌数据(scripts/load_data.py)
- 幂等:TRUNCATE 再灌,重复跑不重复。批量插入:每 10000 行一批(vs 逐行 14 万次往返)。事务:一个 session + commit,整批原子落库(ACID 的 A)。
- 结果:142,905 行,~2.9s。管道:抽取(下载)→转换(strip+归一化)→加载(批量入库)= 真正的 ETL。数据现在**持久化**了。
- EXPLAIN 实测:normalized_name(索引)Index Scan 0.7ms vs organisation_name(无索引)Seq Scan 34ms → **约 48 倍**,O(log n) vs O(n) 落到数字。

### 面试题
- Docker:镜像/容器/卷、为什么用容器(可复现、隔离、贴近生产)、端口映射、卷持久化。
- 数据库:schema/主键/索引、B树怎么加速(排序+平衡树,矮树少寻道)、索引 vs 内存字典(持久化/增量维护)、ORM 是什么、参数化查询防注入。
- ETL:事务/ACID、幂等怎么做、批量插入 vs 逐行、怎么确认索引生效(EXPLAIN ANALYZE 看 Index Scan vs Seq Scan)。

### 第3步 API 读 Postgres(db/index_loader.py + app 的 lifespan)
- 启动时优先从 Postgres 建索引(load_index_from_db),连不上退回 CSV。保留内存匹配器,只换数据源(API 边界让存储与匹配解耦)。
- API 怎么连 Docker 库:API 在宿主机跑,连 localhost:5433(-p 5433:5432 把容器端口发布到本机)。若 API 也进容器,则要用容器名+共享网络(阶段 5)。
- 证明读的是 DB:往库插一条 CSV 没有的行 → /health 142906 且能查到。
- 排错教训:旧 uvicorn 一直占着 8137 端口,新进程起不来 → "改动没生效先查残留旧进程/端口占用"。
