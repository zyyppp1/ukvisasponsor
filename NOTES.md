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
