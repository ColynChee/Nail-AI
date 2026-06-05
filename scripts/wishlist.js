/* ══════════════════════════════════
   WISHLIST
══════════════════════════════════ */
const WISHLIST_API_BASE = 'http://localhost:8000';

function _wishlistSyncAdd(item) {
  if (!window.userClientId) return;
  fetch(`${WISHLIST_API_BASE}/api/wishlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: window.userClientId, ...item }),
  }).catch(e => console.warn('[Wishlist] 同步添加失败:', e.message));
}

function _wishlistSyncRemove(name) {
  if (!window.userClientId) return;
  fetch(`${WISHLIST_API_BASE}/api/wishlist?client_id=${encodeURIComponent(window.userClientId)}&name=${encodeURIComponent(name)}`, {
    method: 'DELETE',
  }).catch(e => console.warn('[Wishlist] 同步删除失败:', e.message));
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

