// Content script:注入 LinkedIn 职位页,自动抓公司名 -> 请 background 调 API ->
// 在右下角注入结果徽章。
//
// 三个真实难点(面试可讲):
//  1) LinkedIn 新版/语义搜索页的 class 名是随机哈希 -> 不能靠 class,改靠稳定结构:
//     指向 /company/ 的链接、取文字干净的那个。
//  2) LinkedIn 是单页应用(SPA):点职位不刷新 -> 周期性重检测,公司名变了才重查。
//  3) 页面 CSP 会拦截往我们 API 的请求 -> 网络请求交给 background service worker
//     (隔离于页面、不受页面 CSP/CORS 约束)。

function isCleanCompany(t) {
  if (!t) return false;
  t = t.trim();
  if (t.length < 2 || t.length > 80) return false;
  // 排除关注数、"Show more"、带大数字等噪声
  if (/followers|following|Show|Premium|·|\d{3,}/i.test(t)) return false;
  return true;
}

function detectCompany() {
  // 1) 经典职位详情页:稳定 class 选择器(存在就优先用)
  const classSelectors = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name a",
    ".artdeco-entity-lockup__subtitle a",
  ];
  for (const sel of classSelectors) {
    const el = document.querySelector(sel);
    const t = el && el.textContent.trim();
    if (isCleanCompany(t)) return t.replace(/\s+/g, " ");
  }
  // 2) 新版/语义搜索页:class 随机哈希,改用结构 —— 第一个文字干净的 /company/ 链接
  for (const a of document.querySelectorAll("a[href*='/company/']")) {
    const t = (a.textContent || "").trim().replace(/\s+/g, " ");
    if (isCleanCompany(t)) return t;
  }
  return null;
}

// —— 徽章(只创建一次,固定右下角)——
let badge = null;
function ensureBadge() {
  if (badge && badge.isConnected) return badge;
  badge = document.createElement("div");
  badge.id = "uvsc-badge";
  Object.assign(badge.style, {
    position: "fixed", right: "16px", bottom: "16px", zIndex: "2147483647",
    maxWidth: "300px", padding: "12px 14px", borderRadius: "10px",
    background: "#ffffff", color: "#012a40", boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
    border: "1px solid #eceff5", font: "13px -apple-system, 'Segoe UI', Arial, sans-serif",
    lineHeight: "1.45",
  });
  document.body.appendChild(badge);
  return badge;
}

function header(company) {
  const h = document.createElement("div");
  h.textContent = `Visa sponsorship · ${company}`;
  Object.assign(h.style, { fontWeight: "700", fontSize: "12px", color: "#012a40" });
  return h;
}

function row(tickText, tickColor, boldText, metaText) {
  const r = document.createElement("div");
  r.style.marginTop = "6px";
  const t = document.createElement("span");
  t.textContent = tickText + " ";
  t.style.color = tickColor;
  t.style.fontWeight = "700";
  const b = document.createElement("b");
  b.textContent = boldText;
  r.append(t, b);
  if (metaText) {
    const m = document.createElement("div");
    m.textContent = metaText;
    m.style.color = "#64748b";
    m.style.fontSize = "11px";
    r.appendChild(m);
  }
  return r;
}

function renderLoading(company) {
  const el = ensureBadge();
  el.textContent = "";
  el.appendChild(header(company));
  const p = document.createElement("div");
  p.textContent = "Checking…";
  p.style.color = "#64748b";
  p.style.marginTop = "6px";
  el.appendChild(p);
}

function renderResult(company, data) {
  const el = ensureBadge();
  el.textContent = "";
  el.appendChild(header(company));
  if (!data.results.length) {
    el.appendChild(row("✗", "#b91c1c", "No licensed sponsor found", "Not in the Home Office register."));
    return;
  }
  const seen = new Set();
  for (const m of data.results) {
    if (seen.has(m.sponsor.name)) continue;
    seen.add(m.sponsor.name);
    const tag = m.method === "exact" ? "exact match" : `${Math.round(m.score)}% match`;
    el.appendChild(row("✓", "#059669", m.sponsor.name, `${m.sponsor.town || "—"} · ${m.sponsor.route} · ${tag}`));
  }
}

function check(company) {
  renderLoading(company);
  // 交给 background service worker 去发请求(绕开页面 CSP/CORS)
  chrome.runtime.sendMessage({ type: "search", company }, (resp) => {
    if (chrome.runtime.lastError) {
      ensureBadge().textContent = "Sponsor checker: background error.";
      return;
    }
    if (!resp || !resp.ok) {
      ensureBadge().textContent = "Sponsor checker: can't reach the API (is uvicorn running on 127.0.0.1:8137?)";
      return;
    }
    renderResult(company, resp.data);
  });
}

// SPA 兜底:每 1.5s 看当前公司名变了没,变了才重查。
let lastCompany = null;
function tick() {
  const company = detectCompany();
  if (company && company !== lastCompany) {
    lastCompany = company;
    check(company);
  }
}
setInterval(tick, 1500);
tick();
