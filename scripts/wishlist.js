/* ══════════════════════════════════
   WISHLIST
══════════════════════════════════ */
function addToWishlist(emoji, name, price, bg, image) {
  if (!wishlist.find(w => w.name === name)) {
    wishlist.push({ emoji, name, price, bg, image: image || '' });
    saveWishlistState();
    updateProfileCounts();
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
  wishlist.splice(i, 1);
  saveWishlistState();
  renderWishlist();
  updateProfileCounts();
  showToast('已移出收藏');
}

