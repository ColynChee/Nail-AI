/* ══════════════════════════════════
   WISHLIST
══════════════════════════════════ */
const WISHLIST_API_BASE = window.API_BASE;

// 把存储的图片地址解析成可显示的 URL：
// - base64 / 完整 http URL：原样
// - 后端托管路径（/designs_generated /user_designs /molds 开头）：补上 API_BASE
// - 其它相对路径（款式图/xxx）：前端直接可访问，原样
function resolveImageSrc(img) {
  if (!img) return '';
  if (img.startsWith('data:') || img.startsWith('http')) return img;
  if (img.startsWith('/designs_generated') || img.startsWith('/user_designs') || img.startsWith('/molds')) {
    return window.API_BASE + img;
  }
  return img;
}

// 收藏同步失败时，把待办存进 localStorage，App 启动或恢复网络时重试
const _PENDING_KEY = 'nailai-wishlist-pending';
function _readPending() {
  try { return JSON.parse(localStorage.getItem(_PENDING_KEY) || '[]'); }
  catch (e) { return []; }
}
function _writePending(list) {
  try { localStorage.setItem(_PENDING_KEY, JSON.stringify(list)); } catch (e) {}
}
function _enqueuePending(op) {  // op = {type:'add', item} or {type:'remove', name}
  const list = _readPending();
  list.push(op);
  _writePending(list);
}

function _wishlistSyncAdd(item) {
  if (!window.userClientId) return;
  fetch(`${WISHLIST_API_BASE}/api/wishlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: window.userClientId, ...item }),
  }).catch(e => {
    console.warn('[Wishlist] 同步添加失败，已加入重试队列:', e.message);
    _enqueuePending({ type: 'add', item });
  });
}

function _wishlistSyncRemove(name) {
  if (!window.userClientId) return;
  fetch(`${WISHLIST_API_BASE}/api/wishlist?client_id=${encodeURIComponent(window.userClientId)}&name=${encodeURIComponent(name)}`, {
    method: 'DELETE',
  }).catch(e => {
    console.warn('[Wishlist] 同步删除失败，已加入重试队列:', e.message);
    _enqueuePending({ type: 'remove', name });
  });
}

// 重试待办队列（启动时 / 网络恢复时调用）
async function flushPendingWishlistOps() {
  if (!window.userClientId) return;
  const list = _readPending();
  if (!list.length) return;
  const remaining = [];
  for (const op of list) {
    try {
      if (op.type === 'add') {
        const r = await fetch(`${WISHLIST_API_BASE}/api/wishlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: window.userClientId, ...op.item }),
        });
        if (!r.ok) remaining.push(op);
      } else if (op.type === 'remove') {
        const r = await fetch(`${WISHLIST_API_BASE}/api/wishlist?client_id=${encodeURIComponent(window.userClientId)}&name=${encodeURIComponent(op.name)}`, { method: 'DELETE' });
        if (!r.ok) remaining.push(op);
      }
    } catch (e) {
      remaining.push(op);
    }
  }
  _writePending(remaining);
  if (list.length !== remaining.length) {
    console.log(`[Wishlist] 重试同步：${list.length - remaining.length} 条成功，${remaining.length} 条仍待重试`);
  }
}

// 网络恢复时自动重试
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => flushPendingWishlistOps());
}

function addToWishlist(emoji, name, price, bg, image, designId) {
  if (!wishlist.find(w => w.name === name)) {
    const item = { emoji, name, price, bg, image: image || '', designId: designId || '' };
    wishlist.push(item);
    saveWishlistState();
    updateProfileCounts();
    _wishlistSyncAdd({ name, emoji, price, bg, image: image || '', design_id: designId || '' });
  }
}

function toggleHeart(btn, name, emoji, price, bg, image, designId) {
  btn.classList.toggle('liked');
  if (btn.classList.contains('liked')) {
    addToWishlist(emoji, name, price, bg, image, designId);
    showToast('已添加到收藏 ♥');
  } else {
    wishlist = wishlist.filter(w => w.name !== name);
    saveWishlistState();
    updateProfileCounts();
    _wishlistSyncRemove(name);
    showToast('已移出收藏');
  }
}

function renderWishlist() {
  const grid = document.getElementById('wishlist-grid');
  const empty = document.getElementById('wishlist-empty');
  if (wishlist.length === 0) {
    grid.innerHTML = '';
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';
  grid.innerHTML = wishlist.map((w,i) => {
    const src = resolveImageSrc(w.image);
    return `
    <div class="wl-card card-press">
      <div class="wl-thumb" style="background:${w.bg}" onclick="goDetail('${w.emoji}','${w.name}','收藏·推荐','${w.price}','${w.bg}','${src}','${w.designId || ''}')">
        ${src ? `<img src="${src}" alt="${w.name}">` : w.emoji}
      </div>
      <div class="wl-info">
        <div class="wl-name">${w.name}</div>
        <div class="wl-row">
          <button class="wl-try" onclick="event.stopPropagation();tryonFromWishlist(${i})">试戴</button>
          <button class="wl-del" onclick="event.stopPropagation();removeWishlist(${i})">✕</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

// 从收藏直接重新试戴该款式
function tryonFromWishlist(i) {
  const w = wishlist[i];
  if (!w) return;
  if (typeof setTryonStyle === 'function') {
    setTryonStyle(w.emoji || '✨', w.name, w.price || 0, w.bg || '#FFF0F5',
                  resolveImageSrc(w.image), w.designId || '');
  }
  if (typeof go === 'function') go('s-tryon');
  if (typeof showToast === 'function') showToast('请上传手部照片开始试戴 ✨');
}

function removeWishlist(i) {
  const removed = wishlist[i];
  wishlist.splice(i, 1);
  saveWishlistState();
  renderWishlist();
  updateProfileCounts();
  if (removed) _wishlistSyncRemove(removed.name);
  showToast('已移出收藏');
}

