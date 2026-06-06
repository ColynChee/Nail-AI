/* ══════════════════════════════════
   账号 / 登录
══════════════════════════════════ */
const AUTH_API_BASE = window.API_BASE;

async function authRegister(username, password) {
  let res;
  try {
    res = await fetch(`${AUTH_API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch (e) {
    throw new Error('服务暂不可用，请稍后重试');
  }
  if (res.status === 409) throw new Error('用户名已存在');
  if (!res.ok) {
    let msg = '注册失败';
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  const data = await res.json();
  setSession({ client_id: data.client_id, username: data.username });
  return data;
}

async function authLogin(username, password) {
  let res;
  try {
    res = await fetch(`${AUTH_API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch (e) {
    throw new Error('服务暂不可用，请稍后重试');
  }
  if (res.status === 401) throw new Error('用户名或密码错误');
  if (!res.ok) {
    let msg = '登录失败';
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  const data = await res.json();
  setSession({ client_id: data.client_id, username: data.username });
  return data;
}

// 首次登录把本地旧收藏合并上传（每个账号只跑一次）
async function migrateLocalWishlistToServer() {
  const cid = window.userClientId;
  if (!cid) return;
  const flagKey = `nailai-migrated-${cid}`;
  if (localStorage.getItem(flagKey)) return;
  const local = readStorage(STORAGE_KEYS.wishlist, []);
  if (Array.isArray(local) && local.length) {
    for (const item of local) {
      try {
        await fetch(`${AUTH_API_BASE}/api/wishlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            client_id: cid,
            name: item.name,
            emoji: item.emoji || '',
            price: item.price || '',
            bg: item.bg || '',
            image: item.image || '',
          }),
        });
      } catch (e) { /* 单条失败忽略 */ }
    }
  }
  try { localStorage.setItem(flagKey, '1'); } catch (e) {}
}

// 从服务端加载收藏，填充内存 wishlist
async function loadWishlistFromServer() {
  const cid = window.userClientId;
  if (!cid) { if (typeof renderWishlist === 'function') renderWishlist(); return; }
  try {
    const res = await fetch(`${AUTH_API_BASE}/api/wishlist?client_id=${encodeURIComponent(cid)}`);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    wishlist = (data.items || []).map(i => ({
      emoji: i.emoji || '', name: i.name, price: i.price || '', bg: i.bg || '', image: i.image || '',
    }));
    if (typeof saveWishlistState === 'function') saveWishlistState();
  } catch (e) {
    console.warn('[Auth] 收藏加载失败，使用本地缓存:', e.message);
  }
  if (typeof renderWishlist === 'function') renderWishlist();
  if (typeof updateProfileCounts === 'function') updateProfileCounts();
}

// 重置个人资料，避免上个账号的本地资料残留；新账号用用户名作昵称
function _resetProfileForAccount(username) {
  userProfile = {
    name: username || '小美同学',
    avatar: (username ? username.trim().charAt(0).toUpperCase() : '小'),
    age: 24,
    skinColorCode: '#F5C6A0',
    skinToneLabel: '自然色',
    skinToneSource: 'preset',
    bio: '美甲爱好者',
    tryonCount: 0,
    bookingCount: 0,
  };
  try { writeStorage(STORAGE_KEYS.profile, userProfile); } catch (e) {}
}

// 登录/注册成功后进入 App
async function enterAppAfterAuth(opts) {
  opts = opts || {};
  // 切换账号先清掉上个账号的本地缓存（除了刚设置的 session）
  // 新账号注册前如果有本地收藏，先迁移到新账号
  if (opts.isNew) {
    await migrateLocalWishlistToServer();
  }
  // 然后清空所有本地用户数据缓存
  try {
    localStorage.removeItem(STORAGE_KEYS.wishlist);
    localStorage.removeItem(STORAGE_KEYS.bookings);
    localStorage.removeItem(STORAGE_KEYS.tryonHistory);
    localStorage.removeItem(STORAGE_KEYS.imageTryonHistory);
  } catch (e) {}
  wishlist = [];
  if (typeof bookings !== 'undefined') bookings = [];
  if (typeof tryonHistory !== 'undefined') tryonHistory = [];
  if (typeof imageTryonHistory !== 'undefined') imageTryonHistory = [];
  // 切换账号先重置资料：新账号用用户名当昵称，登录则清掉旧本地资料等后端覆盖
  _resetProfileForAccount(opts.isNew ? opts.username : null);
  if (typeof bootApp === 'function') await bootApp();
  // 新账号：把用户名作为昵称同步到后端持久化
  if (opts.isNew && typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(e => console.warn('[Auth] 新账号资料同步失败:', e.message));
  }
  if (typeof go === 'function') go('s-home');
}

function doLogout() {
  clearSession();
  // 清掉所有用户私人数据的本地缓存，避免下个账号看到上个人的数据
  try {
    localStorage.removeItem(STORAGE_KEYS.wishlist);
    localStorage.removeItem(STORAGE_KEYS.profile);
    localStorage.removeItem(STORAGE_KEYS.bookings);
    localStorage.removeItem(STORAGE_KEYS.tryonHistory);
    localStorage.removeItem(STORAGE_KEYS.imageTryonHistory);
  } catch (e) {}
  // 重置内存里的状态
  wishlist = [];
  if (typeof bookings !== 'undefined') bookings = [];
  if (typeof tryonHistory !== 'undefined') tryonHistory = [];
  if (typeof imageTryonHistory !== 'undefined') imageTryonHistory = [];
  if (typeof renderWishlist === 'function') renderWishlist();
  if (typeof go === 'function') go('s-login');
}

// ── 登录页表单 ──
let _authMode = 'login';  // login | register

function switchAuthMode(mode) {
  _authMode = mode;
  document.getElementById('auth-tab-login').classList.toggle('active', mode === 'login');
  document.getElementById('auth-tab-register').classList.toggle('active', mode === 'register');
  document.getElementById('auth-submit').textContent = mode === 'login' ? '登录' : '注册';
  document.getElementById('auth-error').textContent = '';
}

async function submitAuth() {
  const username = document.getElementById('auth-username').value.trim();
  const password = document.getElementById('auth-password').value;
  const errEl = document.getElementById('auth-error');
  const btn = document.getElementById('auth-submit');
  errEl.textContent = '';
  if (!username || !password) { errEl.textContent = '请输入用户名和密码'; return; }
  btn.disabled = true;
  btn.textContent = _authMode === 'login' ? '登录中…' : '注册中…';
  try {
    if (_authMode === 'login') {
      const data = await authLogin(username, password);
      await enterAppAfterAuth({ isNew: false, username: data.username });
    } else {
      const data = await authRegister(username, password);
      await enterAppAfterAuth({ isNew: true, username: data.username });
    }
  } catch (e) {
    errEl.textContent = e.message || '操作失败';
  } finally {
    btn.disabled = false;
    btn.textContent = _authMode === 'login' ? '登录' : '注册';
  }
}
