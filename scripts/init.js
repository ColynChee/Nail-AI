/* ══════════════════════════════════
   INIT
══════════════════════════════════ */
loadPersistedState();
applyProfile();
renderGallery('全部');
if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
loadDesignsFromBackend().then(() => {
  // 等待后端数据加载完成后，再刷新热门款式
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  startXhsTrendingRefresh();
});
renderWishlist();
// set default tryon style box
setTryonStyle('🌸','樱花奶油','¥199','#FFF0F5');
