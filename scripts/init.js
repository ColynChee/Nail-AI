/* ══════════════════════════════════
   INIT
══════════════════════════════════ */
loadPersistedState();
applyProfile();
renderGallery('全部');
loadDesignsFromBackend().then(() => {
  // 等待后端数据加载完成后，再刷新热门款式
  startXhsTrendingRefresh();
});
renderWishlist();
// set default tryon style box
setTryonStyle('🌸','樱花奶油','¥199','#FFF0F5');
