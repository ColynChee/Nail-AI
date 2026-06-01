/* ══════════════════════════════════
   NAVIGATION
══════════════════════════════════ */
function go(id, isBack) {
  const prev = document.querySelector('.screen.active');
  const next = document.getElementById(id);
  if (!next || prev === next) return;
  if (prev) {
    prevScreen = prev.id;
    prev.classList.remove('active','back');
  }
  next.classList.remove('back');
  if (isBack) next.classList.add('back');
  next.classList.add('active');
  // side effects
  if (id === 's-wishlist') renderWishlist();
  if (id === 's-profile') applyProfile();
  if (id === 's-gallery') renderGallery(currentFilter);
}

function goBack() { go(prevScreen, true); }

