/* ══════════════════════════════════
   INIT
══════════════════════════════════ */
(async function initApp() {
  loadPersistedState();
  await loadProfileFromBackend();
  applyProfile();
  renderGallery('全部');
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  await loadDesignsFromBackend();
  // 等待后端数据加载完成后，再刷新热门款式
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  startXhsTrendingRefresh();
  renderWishlist();
  // no default style — user must pick one from the gallery
  if (typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(error => console.warn('[Profile] initial sync failed:', error.message));
  }
})();
