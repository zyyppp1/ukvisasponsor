// Content script:注入到 LinkedIn 职位页,自动抓公司名 -> 调 API -> 在页面右下角
// 注入一个结果徽章。
//
// 两个真实难点(面试可讲):
//  1) LinkedIn 的类名会变、按页面类型不同 —— 所以用"多选择器兜底",不押注单一选择器。
//  2) LinkedIn 是单页应用(SPA):点不同职位不刷新页面,只换内容 —— 所以不能只跑一次,
//     要周期性重新检测,公司名变了就重查。

const API = "http://127.0.0.1:8137";

// 公司名的候选选择器(从上到下试,命中即用)。LinkedIn 改版时,加/换这里即可。
const COMPANY_SELECTORS = [
  ".job-details-jobs-unified-top-card__company-name a",
  ".job-details-jobs-unified-top-card__company-name",
  ".jobs-unified-top-card__company-name a",
  ".jobs-unified-top-card__company-name",
  ".artdeco-entity-lockup__subtitle a",
  ".artdeco-entity-lockup__subtitle",
];

function detectCompany() {
  for (const sel of COMPANY_SELECTORS) {
    const el = document.querySelector(sel);
    const text = el && el.textContent.trim();
    if (text && text.length > 1) return text;
  }
  return null;
}

// —— 徽章(只创建一次,固定在右下角)——
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

// 用 textContent 拼元素,避免把数据当 HTML 注入(安全习惯)
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

function header(company) {
  const h = document.createElement("div");
  h.textContent = `Visa sponsorship · ${company}`;
  h.style.fontWeight = "700";
  h.style.fontSize = "12px";
  h.style.color = "#012a40";
  return h;
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

async function check(company) {
  renderLoading(company);
  try {
    const resp = await fetch(`${API}/search?q=${encodeURIComponent(company)}&limit=3`);
    if (!resp.ok) {
      ensureBadge().textContent = `Sponsor check error: HTTP ${resp.status}`;
      return;
    }
    renderResult(company, await resp.json());
  } catch (err) {
    ensureBadge().textContent = "Sponsor checker: can't reach the API (is it running on 127.0.0.1:8137?)";
  }
}

// SPA 兜底:每 1.5s 看当前职位的公司名变了没,变了就重查。
// (更"高级"的做法是 MutationObserver 或监听 history 变化,这里先用最简单可靠的轮询。)
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
