/* ══════════════════════════════════
   今日热门 - 小红书实时数据
══════════════════════════════════ */
let liveTrendingItems = [];
let xhsTrendingState = {
  status: 'idle',
  message: '正在获取小红书实时热度...',
  updatedAt: ''
};
let xhsTrendingTimer;

function getXhsTrendingEndpoint() {
  return (typeof XHS_TRENDING_CONFIG !== 'undefined' && XHS_TRENDING_CONFIG.endpoint || '').trim();
}

function getXhsRefreshMs() {
  const ms = typeof XHS_TRENDING_CONFIG !== 'undefined' ? XHS_TRENDING_CONFIG.refreshMs : 0;
  return Number.isFinite(ms) && ms > 0 ? ms : 5 * 60 * 1000;
}

function shouldUseKeywordFallback() {
  return (
    typeof XHS_TRENDING_CONFIG !== 'undefined' &&
    XHS_TRENDING_CONFIG.keywordFallback !== false &&
    typeof XHS_KEYWORD_HEAT !== 'undefined' &&
    Array.isArray(XHS_KEYWORD_HEAT)
  );
}

function getKeywordHeatEntry(keyword) {
  return XHS_KEYWORD_HEAT.find(item => item.keyword === keyword);
}

function getStyleKeywordList(style) {
  if (typeof XHS_STYLE_KEYWORDS !== 'undefined' && XHS_STYLE_KEYWORDS[style.name]) {
    return XHS_STYLE_KEYWORDS[style.name];
  }
  return [style.name, ...style.tags.map(tag => `${tag}美甲`)];
}

function buildKeywordHeatTrendingItems() {
  return STYLES.map(style => {
    const keywords = getStyleKeywordList(style);
    const entries = keywords.map(getKeywordHeatEntry).filter(Boolean);
    const score = entries.reduce((sum, item) => sum + item.score, 0);
    const topEntry = entries.sort((a, b) => b.score - a.score)[0];
    const topKeywords = entries.slice(0, 2).map(item => item.keyword).join(' · ');
    return {
      rank: 0,
      name: style.name,
      sub: topKeywords || `${style.tags[0]} · 关键词热度`,
      price: style.price,
      heat: `${formatXhsHeat(score)}参考`,
      heatScore: score,
      emoji: style.emoji,
      bg: style.bg,
      image: style.image,
      detailed_image: style.detailed_image,
      id: style.id,
      xhs: topEntry ? topEntry.xhs : 'https://www.xiaohongshu.com/search_result?keyword=%E7%BE%8E%E7%94%B2'
    };
  })
    .filter(item => item.heatScore > 0)
    .sort((a, b) => b.heatScore - a.heatScore)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function buildKeywordHeatGalleryItems(filter) {
  const styles = filter === '全部' ? STYLES : STYLES.filter(style => style.tags.includes(filter));
  return styles.map(style => {
    const keywords = getStyleKeywordList(style);
    const entries = keywords
      .map(getKeywordHeatEntry)
      .filter(Boolean)
      .sort((a, b) => b.score - a.score);
    const score = entries.reduce((sum, item) => sum + item.score, 0);
    const topEntry = entries[0];
    const topKeywords = entries.slice(0, 2).map(item => item.keyword).join(' · ');
    return {
      ...style,
      sub: topKeywords || `${style.tags[0]} · 关键词热度`,
      heat: score ? `${formatXhsHeat(score)}参考` : `${style.heat} 热度`,
      heatScore: score || toTrafficNumber(style.heat),
      xhs: topEntry ? topEntry.xhs : 'https://www.xiaohongshu.com/search_result?keyword=%E7%BE%8E%E7%94%B2'
    };
  })
    .sort((a, b) => b.heatScore - a.heatScore)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function getLocalStyleMatch(item) {
  const name = item.localName || item.name || item.keyword || '';
  return STYLES.find(style => (
    style.name === name ||
    name.includes(style.name) ||
    style.name.includes(name)
  ));
}

function toTrafficNumber(value) {
  if (typeof value === 'number') return value;
  if (!value) return 0;
  const text = String(value).trim().toLowerCase();
  const num = Number.parseFloat(text.replace(/[^\d.]/g, ''));
  if (!Number.isFinite(num)) return 0;
  if (text.includes('w') || text.includes('万')) return num * 10000;
  if (text.includes('k')) return num * 1000;
  return num;
}

function calcXhsHeatScore(item) {
  if (item.heatScore !== undefined) return toTrafficNumber(item.heatScore);
  const views = toTrafficNumber(item.viewCount || item.views || item.readCount);
  const likes = toTrafficNumber(item.likeCount || item.likes);
  const collects = toTrafficNumber(item.collectCount || item.collects || item.favorites);
  const comments = toTrafficNumber(item.commentCount || item.comments);
  const notes = toTrafficNumber(item.noteCount || item.notes);
  return views + likes * 6 + collects * 8 + comments * 10 + notes * 12;
}

function formatXhsHeat(score) {
  if (!score) return '实时热度';
  if (score >= 10000) return `${(score / 10000).toFixed(1)}w 热度`;
  if (score >= 1000) return `${(score / 1000).toFixed(1)}k 热度`;
  return `${Math.round(score)} 热度`;
}

function normalizeXhsTrendingItem(item, index) {
  const local = getLocalStyleMatch(item) || {};
  const score = calcXhsHeatScore(item);
  return {
    rank: index + 1,
    name: item.name || item.title || item.keyword || local.name || '小红书热门款',
    sub: item.sub || item.category || item.reason || '小红书实时热度',
    price: item.price || local.price || '到店咨询',
    heat: item.heat || formatXhsHeat(score),
    heatScore: score,
    emoji: item.emoji || local.emoji || '💅',
    bg: item.bg || local.bg || '#FFF0F5',
    image: item.image || item.imageUrl || item.cover || local.image || '',
    xhs: item.xhs || item.xhsUrl || item.url || 'https://www.xiaohongshu.com/search_result?keyword=%E7%BE%8E%E7%94%B2'
  };
}

function normalizeXhsTrendingPayload(payload) {
  const rows = Array.isArray(payload) ? payload : (payload.items || payload.data || []);
  return rows
    .map(normalizeXhsTrendingItem)
    .sort((a, b) => b.heatScore - a.heatScore)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function renderTrendMessage(title, text) {
  return `
    <div class="data-empty trend-empty">
      <div class="data-empty-title">${title}</div>
      <div class="data-empty-text">${text}</div>
    </div>`;
}

function renderTrendingCards(items, limit) {
  return items.slice(0, limit).map((item, i) => `
    <div class="trend-card" onclick="goDetail('${item.emoji}','${item.name}','${item.sub}','${item.price}','${item.bg}','${item.image}','${item.id || ''}')"> 
      <div class="trend-thumb">
        ${item.image ? `<img src="${item.image}" alt="${item.name}">` : item.emoji}
        <div class="rank-badge">#${item.rank}</div>
        ${i === 0 ? '<div class="hot-badge">热</div>' : ''}
      </div>
      <div class="trend-info">
        <div class="trend-name">${item.name}</div>
        <div class="trend-sub">${item.sub}</div>
        <div class="trend-foot">
          <span class="trend-heat">${item.heat}</span>
          <button class="mini-try" onclick="event.stopPropagation();setTryonStyle('${item.emoji}','${item.name}','${item.price}','${item.bg}','${item.image}');go('s-tryon')">试戴</button>
        </div>
        <a class="xhs-link" href="${item.xhs}" target="_blank" rel="noopener" onclick="event.stopPropagation()">小红书搜词</a>
      </div>
    </div>`).join('');
}

function updateTrendNote() {
  const note = document.getElementById('trend-note');
  if (!note) return;
  if (xhsTrendingState.status !== 'ready') {
    note.textContent = '';
    return;
  }
  if (xhsTrendingState.source === 'keyword') {
    note.textContent = `小红书关键词热度参考 · 更新于 ${xhsTrendingState.updatedAt} · 可在 scripts/xhs-keyword-heat.js 调整分数`;
    return;
  }
  note.textContent = `小红书授权数据 · 更新于 ${xhsTrendingState.updatedAt || '刚刚'}`;
}

function paintTrendingHome() {
  const grid = document.getElementById('trend-grid');
  if (!grid) return;
  updateTrendNote();
  if (xhsTrendingState.status === 'loading') {
    grid.innerHTML = renderTrendMessage('正在同步小红书热度', '连接实时数据源后会自动按流量排序。');
    return;
  }
  if (xhsTrendingState.status !== 'ready') {
    grid.innerHTML = renderTrendMessage('未接入小红书实时数据源', xhsTrendingState.message);
    return;
  }
  grid.innerHTML = renderTrendingCards(liveTrendingItems, 4);
}

async function refreshXhsTrending() {
  const endpoint = getXhsTrendingEndpoint();
  if (!endpoint) {
    if (shouldUseKeywordFallback()) {
      liveTrendingItems = buildKeywordHeatTrendingItems();
      xhsTrendingState = {
        status: liveTrendingItems.length ? 'ready' : 'empty',
        message: liveTrendingItems.length ? '' : '关键词热度表还没有可匹配的款式。',
        updatedAt: typeof XHS_KEYWORD_HEAT_UPDATED_AT !== 'undefined' ? XHS_KEYWORD_HEAT_UPDATED_AT : '手动更新',
        source: 'keyword'
      };
    } else {
      liveTrendingItems = [];
      xhsTrendingState = {
        status: 'unconfigured',
        message: '请在 scripts/xhs-config.js 填入你自己的小红书授权数据接口，或开启 keywordFallback。',
        updatedAt: ''
      };
    }
    paintTrendingHome();
    if (currentFilter === '热门') renderGallery('热门');
    return;
  }

  xhsTrendingState = {
    status: 'loading',
    message: '正在获取小红书实时热度...',
    updatedAt: ''
  };
  paintTrendingHome();

  try {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    liveTrendingItems = normalizeXhsTrendingPayload(payload);
    xhsTrendingState = {
      status: liveTrendingItems.length ? 'ready' : 'empty',
      message: liveTrendingItems.length ? '' : '实时接口已连接，但暂时没有返回美甲热门数据。',
      updatedAt: payload.updatedAt || new Date().toISOString(),
      source: 'official'
    };
  } catch (error) {
    liveTrendingItems = [];
    xhsTrendingState = {
      status: 'error',
      message: `小红书实时数据获取失败：${error.message}`,
      updatedAt: ''
    };
  }

  paintTrendingHome();
  if (currentFilter === '热门') renderGallery('热门');
}

function startXhsTrendingRefresh() {
  refreshXhsTrending();
  clearInterval(xhsTrendingTimer);
  xhsTrendingTimer = setInterval(refreshXhsTrending, getXhsRefreshMs());
}

function getLiveTrendingItems() {
  return liveTrendingItems;
}

function getLiveTrendingState() {
  return xhsTrendingState;
}

function openTrendingGallery() {
  currentFilter = '热门';
  syncGalleryFilterChip('热门');
  go('s-gallery');
  renderGallery('热门');
}

function syncGalleryFilterChip(filter) {
  document.querySelectorAll('#filter-row .chip').forEach(chip => {
    chip.classList.toggle('on', chip.textContent.trim() === filter);
  });
}

