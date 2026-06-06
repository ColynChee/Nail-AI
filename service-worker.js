/* 指上谈兵 PWA Service Worker */
// 改版本号会让所有用户拿到新缓存（每次大改 CSS/JS 都 bump 这里）
const CACHE = 'zhishangtanbing-v2-bubblegum';

// 预缓存应用外壳（核心静态文件）
const SHELL = [
  './',
  './nailai.html',
  './manifest.json',
  './styles/main.css?v=bubblegum1',
  './assets/logo-nobg.png',
  './assets/icon-192.png',
  './assets/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // 只处理 GET；后端 API、跨域请求一律走网络（不缓存动态数据）
  if (req.method !== 'GET') return;
  if (url.pathname.includes('/api/')) return;
  if (url.origin !== self.location.origin) return;

  // 静态资源：缓存优先，回退网络，并把新资源写入缓存
  e.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.status === 200 && res.type === 'basic') {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
