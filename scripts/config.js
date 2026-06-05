/* ══════════════════════════════════
   全局配置 —— 后端地址
   ──────────────────────────────────
   本地开发自动用 localhost；部署后访问线上域名时，
   请把下面的 PROD_API_BASE 改成你的云端后端地址。
══════════════════════════════════ */
(function () {
  // 👉 部署后端后，把这里改成你的后端 HTTPS 地址（如 https://nailai-api.onrender.com）
  const PROD_API_BASE = 'https://REPLACE-WITH-YOUR-BACKEND-URL';

  const host = location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1' || host === '';

  window.API_BASE = isLocal ? 'http://localhost:8000' : PROD_API_BASE;
  console.log('[Config] API_BASE =', window.API_BASE);
})();
