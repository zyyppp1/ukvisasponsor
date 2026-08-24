// 弹窗逻辑:输入公司名 -> 调本地 API -> 显示候选担保方。
// 这是"从前端发 HTTP"的最小示范:fetch + async/await + 渲染到 DOM。

const API = "http://127.0.0.1:8137";

const input = document.getElementById("q");
const button = document.getElementById("go");
const results = document.getElementById("results");

async function search() {
  const q = input.value.trim();
  if (!q) return;
  results.textContent = "Searching…";

  try {
    // fetch 发一个 GET 请求;await 等它回来。encodeURIComponent 处理空格/特殊字符。
    const resp = await fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=5`);
    if (!resp.ok) {
      results.textContent = `Error: HTTP ${resp.status}`;
      return;
    }
    const data = await resp.json();   // 把 JSON 响应体解析成 JS 对象
    render(data);
  } catch (err) {
    // 网络层失败(通常是 API 没启动)
    results.textContent = "Can't reach the API. Is it running on 127.0.0.1:8137?";
  }
}

function render(data) {
  results.textContent = "";
  if (!data.results.length) {
    results.textContent = `No licensed sponsor found for “${data.query}”.`;
    return;
  }

  // 同公司多路线会重复,按名字去重展示(呼应之前说的"待打磨点①")
  const seen = new Set();
  for (const m of data.results) {
    if (seen.has(m.sponsor.name)) continue;
    seen.add(m.sponsor.name);

    // 用 textContent 构建元素,避免把数据当 HTML 注入(安全习惯)
    const row = document.createElement("div");
    row.className = "row";

    const tick = document.createElement("span");
    tick.className = "ok";
    tick.textContent = "✓ ";

    const name = document.createElement("b");
    name.textContent = m.sponsor.name;

    const meta = document.createElement("div");
    meta.className = "meta";
    const tag = m.method === "exact" ? "exact match" : `${Math.round(m.score)}% match`;
    meta.textContent = `${m.sponsor.town || "—"} · ${m.sponsor.route} · ${tag}`;

    row.append(tick, name, meta);
    results.appendChild(row);
  }
}

button.addEventListener("click", search);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
