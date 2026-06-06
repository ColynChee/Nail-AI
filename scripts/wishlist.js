/* ══════════════════════════════════
   WISHLIST
══════════════════════════════════ */
const WISHLIST_API_BASE = window.API_BASE;

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

function addToWishlist(emoji, name, price, bg, image) {
  if (!wishlist.find(w => w.name === name)) {
    wishlist.push({ emoji, name, price, bg, image: image || '' });
    saveWishlistState();
    updateProfileCounts();
    _wishlistSyncAdd({ name, emoji, price, bg, image: image || '' });
  }
}

function toggleHeart(btn, name, emoji, price, bg, image) {
  btn.classList.toggle('liked');
  if (btn.classList.contains('liked')) {
    addToWishlist(emoji, name, price, bg, image);
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
  grid.innerHTML = wishlist.map((w,i) => `
    <div class="wl-card card-press" onclick="goDetail('${w.emoji}','${w.name}','收藏·推荐','${w.price}','${w.bg}','${w.image || ''}')">
      <div class="wl-thumb" style="background:${w.bg}">
        ${w.image ? `<img src="${w.image}" alt="${w.name}">` : w.emoji}
      </div>
      <div class="wl-info">
        <div class="wl-name">${w.name}</div>
        <div class="wl-row">
          <span class="wl-price">${w.price}</span>
          <button class="wl-del" onclick="event.stopPropagation();removeWishlist(${i})">✕</button>
        </div>
      </div>
    </div>`).join('');
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

