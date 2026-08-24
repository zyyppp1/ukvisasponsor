// Background service worker:专管网络请求。它独立于任何网页运行,靠 host_permissions
// 访问我们的 API,既不受 LinkedIn 页面 CSP 约束,也不受 CORS 限制。这是 MV3 里
// "从扩展发跨源请求"的规范位置。

const API = "http://127.0.0.1:8137";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "search") {
    fetch(`${API}/search?q=${encodeURIComponent(msg.company)}&limit=3`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // 告诉 Chrome:我会异步调用 sendResponse,别提前关掉通道
  }
});
