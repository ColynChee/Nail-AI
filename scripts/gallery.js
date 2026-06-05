/* ══════════════════════════════════
   GALLERY
══════════════════════════════════ */
function updateGalleryHeatNote(filter) {
  const note = document.getElementById('gallery-note');
  if (!note) return;
  const state = typeof getLiveTrendingState === 'function' ? getLiveTrendingState() : {};
  const updatedAt = typeof formatUpdatedAt === 'function'
    ? formatUpdatedAt(state.updatedAt)
    : (state.updatedAt || '本地款式库');
  if (filter === '热门' && state.status === 'ready') {
    const sourceName = state.source === 'bilibili-live' ? 'B站' : '平台';
    note.textContent = `热门榜按${sourceName}热度排序 · 更新于 ${updatedAt}`;
    return;
  }
  const label = filter === '全部' ? '全部款式' : `${filter}款式`;
  if (state.status === 'ready') {
    const sourceName = state.source === 'bilibili-live' ? 'B站实时热度' : '平台实时热度';
    note.textContent = `${label}优先按${sourceName}排序 · 更新于 ${updatedAt}`;
    return;
  }
  note.textContent = `${label}按款式库热度排序 · 更新于 ${updatedAt}`;
}

function galleryHeatNumber(value) {
  if (typeof toTrafficNumber === 'function') return toTrafficNumber(value);
  const text = String(value || '').trim().toLowerCase();
  const num = Number.parseFloat(text.replace(/[^\d.]/g, ''));
  if (!Number.isFinite(num)) return 0;
  if (text.includes('w') || text.includes('万')) return num * 10000;
  if (text.includes('k')) return num * 1000;
  return num;
}

function galleryItemsByFilter(filter) {
  const base = filter === '全部' ? STYLES : STYLES.filter(s => Array.isArray(s.tags) && s.tags.includes(filter));
  const liveItems = typeof getLiveTrendingItems === 'function' ? getLiveTrendingItems() : [];
  const liveById = new Map(liveItems.filter(item => item.id).map(item => [item.id, item]));
  const liveByName = new Map(liveItems.filter(item => item.name).map(item => [item.name, item]));
  return base
    .map(style => {
      const live = liveById.get(style.id) || liveByName.get(style.name);
      if (!live) return { ...style, heatScore: galleryHeatNumber(style.heat), heatSource: 'local' };
      const liveHeat = live.heat || (typeof formatXhsHeat === 'function' ? formatXhsHeat(live.heatScore) : style.heat);
      return {
        ...style,
        ...live,
        id: style.id,
        name: style.name,
        price: style.price,
        tags: style.tags,
        bg: style.bg,
        image: style.image,
        detailed_image: style.detailed_image,
        heat: liveHeat,
        heatScore: galleryHeatNumber(live.heatScore || liveHeat || style.heat),
        heatSource: live.trendSource || 'live'
      };
    })
    .sort((a, b) => galleryHeatNumber(b.heatScore || b.heat) - galleryHeatNumber(a.heatScore || a.heat))
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function renderGallery(filter) {
  const grid = document.getElementById('gallery-grid');
  updateGalleryHeatNote(filter);
  if (filter === '热门') {
    // 用全部款式按热度排序，渲染成和首页「今日热门」一样的 trend-card 样式
    const hotItems = galleryItemsByFilter('全部').map(s => ({
      ...s,
      sub: s.sub || (Array.isArray(s.tags) ? s.tags.slice(0, 2).join(' · ') : ''),
    }));
    grid.className = 'gallery-grid trend-grid';
    if (typeof renderTrendingCards === 'function') {
      grid.innerHTML = renderTrendingCards(hotItems, hotItems.length);
    }
    return;
  }
  grid.className = 'gallery-grid';
  const items = galleryItemsByFilter(filter);
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

// ── 首页搜索 ──────────────────────────
let _searchTimer = null;

function handleHomeSearch(query, immediate) {
  clearTimeout(_searchTimer);
  const delay = immediate ? 0 : 300;
  _searchTimer = setTimeout(() => {
    const q = (query || '').trim();
    if (!q) return; // 空则不跳转
    go('s-gallery');
    renderSearchResults(q);
    // 去掉所有 chip 高亮，显示搜索状态
    if (typeof syncGalleryFilterChip === 'function') syncGalleryFilterChip('');
    const note = document.getElementById('gallery-note');
    if (note) note.textContent = `搜索"${q}"的结果`;
  }, delay);
}

function renderSearchResults(query) {
  const grid = document.getElementById('gallery-grid');
  if (!grid) return;
  grid.className = 'gallery-grid';
  const q = query.toLowerCase();
  const results = STYLES.filter(s => {
    const text = [s.name, ...(s.tags || []), s.price || ''].join(' ').toLowerCase();
    return q.split(/\s+/).every(word => text.includes(word));
  });
  if (!results.length) {
    grid.innerHTML = `<div class="data-empty gallery-empty" style="grid-column:1/-1">
      <div class="data-empty-title">没有找到相关款式</div>
      <div class="data-empty-text">试试其他关键词，比如颜色、风格或形状</div>
    </div>`;
    return;
  }
  grid.innerHTML = results.map((s, i) => `
    <div class="g-card card-press" onclick="goDetail('${s.emoji}','${s.name}','${(s.tags||[]).slice(0,2).join('·')}','${s.price}','${s.bg}','${s.image||''}','${s.id||''}')">
      <div class="g-thumb" style="background:${s.bg}">
        ${s.image ? `<img src="${s.image}" alt="${s.name}">` : s.emoji}
      </div>
      <div class="g-info">
        <div class="g-name">${s.name}</div>
        <div class="g-meta">
          <span class="g-price">${s.price}</span>
          <span class="g-heat">${s.heat||''}</span>
        </div>
      </div>
    </div>`).join('');
}
