/* ══════════════════════════════════
   INIT
══════════════════════════════════ */
async function bootApp() {
  loadPersistedState();
  // 登录会话覆盖匿名 client_id（必须在任何后端调用前）
  const session = (typeof getSession === 'function') ? getSession() : null;
  if (session && session.client_id) window.userClientId = session.client_id;

  await loadProfileFromBackend();
  applyProfile();
  renderGallery('全部');
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  await loadDesignsFromBackend();
  // 等待后端数据加载完成后，再刷新热门款式
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  startXhsTrendingRefresh();
  // 收藏从服务端加载（失败回退本地缓存）
  if (typeof loadWishlistFromServer === 'function') await loadWishlistFromServer();
  else renderWishlist();
  // no default style — user must pick one from the gallery
  if (typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(error => console.warn('[Profile] initial sync failed:', error.message));
  }
}

// 登录闸门：无 session 则只显示登录页，不启动 App
(function gate() {
  const session = (typeof getSession === 'function') ? getSession() : null;
  if (session && session.client_id) {
    window.userClientId = session.client_id;
    go('s-home');
    bootApp();
  } else {
    go('s-login');
  }
})();
