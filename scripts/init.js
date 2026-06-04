/* ══════════════════════════════════
   INIT
══════════════════════════════════ */
(async function initApp() {
  loadPersistedState();
  await loadProfileFromBackend();
  applyProfile();
  renderGallery('全部');
  await loadDesignsFromBackend();
  startXhsTrendingRefresh();
  renderWishlist();
  // set default tryon style box
  setTryonStyle('🌸','樱花奶油','¥199','#FFF0F5');
  if (typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(error => console.warn('[Profile] initial sync failed:', error.message));
  }
})();
