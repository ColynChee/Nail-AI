/* ══════════════════════════════════
   GALLERY
══════════════════════════════════ */
function updateGalleryHeatNote(filter) {
  const note = document.getElementById('gallery-note');
  if (!note) return;
  const state = typeof getLiveTrendingState === 'function' ? getLiveTrendingState() : {};
  const updatedAt = state.updatedAt || (typeof XHS_KEYWORD_HEAT_UPDATED_AT !== 'undefined' ? XHS_KEYWORD_HEAT_UPDATED_AT : '手动更新');
  const sourceName = state.source === 'bilibili-live' ? 'B站' : '平台';
  if (filter === '热门') {
    note.textContent = `热门榜按${sourceName}热度排序 · 更新于 ${updatedAt}`;
    return;
  }
  note.textContent = `${filter}款式按${sourceName}关键词热度排序 · 更新于 ${updatedAt}`;
}

function renderGallery(filter) {
  const grid = document.getElementById('gallery-grid');
  updateGalleryHeatNote(filter);
  if (filter === '热门') {
    const liveItems = typeof getLiveTrendingItems === 'function' ? getLiveTrendingItems() : [];
    if (!liveItems.length) {
      const state = typeof getLiveTrendingState === 'function' ? getLiveTrendingState() : {};
      grid.innerHTML = `
        <div class="data-empty gallery-empty">
          <div class="data-empty-title">${state.status === 'loading' ? '正在同步平台热度' : '未接入平台实时数据源'}</div>
          <div class="data-empty-text">${state.message || '请先配置授权后的实时数据接口，或添加公开视频链接。'}</div>
        </div>`;
      return;
    }
    grid.innerHTML = liveItems.map(s => `
      <div class="g-card card-press" onclick="goDetail('${s.emoji}','${s.name}','${s.sub}','${s.price}','${s.bg}','${s.image || ''}','${s.id || ''}')">
        <div class="g-thumb" style="background:${s.bg}">
          ${s.image ? `<img src="${s.image}" alt="${s.name}">` : s.emoji}
          <div class="rank-badge">#${s.rank}</div>
          ${s.rank === 1 ? '<div class="hot-badge">热</div>' : ''}
        </div>
        <div class="g-info">
          <div class="g-name">${s.name}</div>
          <div class="g-meta">
            <span class="g-price">${s.price}</span>
            <span class="g-heat">${s.heat}</span>
          </div>
        </div>
      </div>`).join('');
    return;
  }
  const items = typeof buildKeywordHeatGalleryItems === 'function'
    ? buildKeywordHeatGalleryItems(filter)
    : (filter === '全部' ? STYLES : STYLES.filter(s => s.tags.includes(filter)));
  grid.innerHTML = items.map((s,i) => `
    <div class="g-card card-press" onclick="goDetail('${s.emoji}','${s.name}','${s.sub || `${s.tags[0]}·${s.tags[1]||s.tags[0]}`}','${s.price}','${s.bg}','${s.image || ''}','${s.id || ''}')">
      <div class="g-thumb" style="background:${s.bg}">
        ${s.image ? `<img src="${s.image}" alt="${s.name}">` : s.emoji}
        ${i < 3 ? '<div class="rank-badge">#'+s.rank+'</div>' : ''}
        ${i===0?'<div class="hot-badge">热</div>':''}
      </div>
      <div class="g-info">
        <div class="g-name">${s.name}</div>
        <div class="g-meta">
          <span class="g-price">${s.price}</span>
          <span class="g-heat">${s.heat}</span>
        </div>
      </div>
    </div>`).join('');
}

function filterGallery(filter, btn) {
  currentFilter = filter;
  if (typeof syncGalleryFilterChip === 'function') {
    syncGalleryFilterChip(filter);
  } else {
    document.querySelectorAll('#filter-row .chip').forEach(c => c.classList.remove('on'));
    btn.classList.add('on');
  }
  renderGallery(filter);
}
