/* ══════════════════════════════════
   今日热门 - 平台实时数据
══════════════════════════════════ */
let liveTrendingItems = [];
let xhsTrendingState = {
  status: 'idle',
  message: '正在获取平台实时热度...',
  updatedAt: ''
};
let xhsTrendingTimer;

function formatUpdatedAt(raw) {
  if (!raw) return '刚刚';
  const d = new Date(raw);
  if (isNaN(d)) return raw; // not a date string, return as-is
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const todayStr = now.toDateString();
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === todayStr) return `今天 ${time}`;
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`;
  return `${d.getMonth() + 1}月${d.getDate()}日 ${time}`;
}

function getDouyinTrendingConfig() {
  if (typeof DOUYIN_TRENDING_CONFIG !== 'undefined') return DOUYIN_TRENDING_CONFIG;
  if (typeof XHS_TRENDING_CONFIG !== 'undefined') return XHS_TRENDING_CONFIG;
  return {};
}

function getXhsTrendingEndpoint() {
  return (getDouyinTrendingConfig().endpoint || '').trim();
}

function getXhsRefreshMs() {
  const ms = getDouyinTrendingConfig().refreshMs || 0;
  return Number.isFinite(ms) && ms > 0 ? ms : 5 * 60 * 1000;
}

function shouldUseKeywordFallback() {
  return (
    getDouyinTrendingConfig().keywordFallback !== false &&
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
      douyin: topEntry ? (topEntry.douyin || topEntry.xhs) : 'https://www.douyin.com/search/%E7%BE%8E%E7%94%B2',
      xhs: topEntry ? (topEntry.douyin || topEntry.xhs) : 'https://www.douyin.com/search/%E7%BE%8E%E7%94%B2'
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
      douyin: topEntry ? (topEntry.douyin || topEntry.xhs) : 'https://www.douyin.com/search/%E7%BE%8E%E7%94%B2',
      xhs: topEntry ? (topEntry.douyin || topEntry.xhs) : 'https://www.douyin.com/search/%E7%BE%8E%E7%94%B2'
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
  const views = toTrafficNumber(item.viewCount || item.views || item.readCount || item.playCount || item.play_count);
  const likes = toTrafficNumber(item.likeCount || item.likes || item.diggCount || item.digg_count);
  const collects = toTrafficNumber(item.collectCount || item.collects || item.favorites || item.favoriteCount);
  const comments = toTrafficNumber(item.commentCount || item.comments);
  const shares = toTrafficNumber(item.shareCount || item.shares);
  const notes = toTrafficNumber(item.noteCount || item.notes);
  return views + likes * 6 + collects * 8 + comments * 10 + shares * 12 + notes * 12;
}

function formatXhsHeat(score) {
  if (!score) return '实时热度';
  if (score >= 10000) return `${(score / 10000).toFixed(1)}w 热度`;
  if (score >= 1000) return `${(score / 1000).toFixed(1)}k 热度`;
  return `${Math.round(score)} 热度`;
}

function formatXhsMetric(value) {
  const num = toTrafficNumber(value);
  if (!num) return '0';
  if (num >= 10000) return `${(num / 10000).toFixed(1)}w`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
  return `${Math.round(num)}`;
}

function renderDouyinStats(item) {
  const stats = item.rawStats || {};
  const total = toTrafficNumber(stats.viewCount) + toTrafficNumber(stats.likeCount) +
    toTrafficNumber(stats.collectCount) + toTrafficNumber(stats.commentCount) +
    toTrafficNumber(stats.shareCount) + toTrafficNumber(stats.noteCount);
  if (!total && item.trendSource === 'local-fallback') {
    if (item.crawlerStatus === 'login_required') {
      return '<div class="trend-stats"><span>视频需登录 · 使用本地热度参考</span></div>';
    }
    if (item.crawlerStatus === 'video_not_public') {
      return '<div class="trend-stats"><span>视频不公开 · 使用本地热度参考</span></div>';
    }
    if (item.crawlerStatus === 'unconfigured') {
      return '<div class="trend-stats"><span>未接入公开视频 · 使用本地热度参考</span></div>';
    }
    if (item.crawlerStatus === 'not_discovered') {
      return '<div class="trend-stats"><span>未自动发现视频 · 使用本地热度参考</span></div>';
    }
    return '<div class="trend-stats"><span>公开统计隐藏 · 使用本地热度参考</span></div>';
  }
  if (!total && item.crawlerStatus === 'login_required') {
    return '<div class="trend-stats"><span>视频需登录，无法读取实时统计</span></div>';
  }
  if (!total && item.crawlerStatus === 'video_not_public') {
    return '<div class="trend-stats"><span>视频不公开，无法读取实时统计</span></div>';
  }
  if (!total && item.crawlerStatus === 'no_public_stats_found') {
    return '<div class="trend-stats"><span>公开视频未暴露统计</span></div>';
  }
  if (!total && item.crawlerStatus === 'error') {
    return '<div class="trend-stats"><span>公开页面暂不可读</span></div>';
  }
  if (!total) return '';
  const collectText = toTrafficNumber(stats.collectCount) ? `<span>藏 ${formatXhsMetric(stats.collectCount)}</span>` : '';
  const danmakuText = toTrafficNumber(stats.danmakuCount) ? `<span>弹 ${formatXhsMetric(stats.danmakuCount)}</span>` : '';
  const shareText = toTrafficNumber(stats.shareCount) ? `<span>转 ${formatXhsMetric(stats.shareCount)}</span>` : '';
  return `
    <div class="trend-stats">
      <span>播放 ${formatXhsMetric(stats.viewCount)}</span>
      <span>赞 ${formatXhsMetric(stats.likeCount)}</span>
      <span>评 ${formatXhsMetric(stats.commentCount)}</span>
      ${collectText}
      ${danmakuText}
      ${shareText}
    </div>`;
}

function normalizeXhsTrendingItem(item, index) {
  const local = getLocalStyleMatch(item) || {};
  const score = calcXhsHeatScore(item);
  return {
    rank: index + 1,
    id: item.id || item.design_id || item.designId || local.id || '',
    name: item.name || item.title || item.keyword || local.name || '平台热门款',
    sub: item.sub || item.category || item.reason || '平台实时热度',
    price: item.price || local.price || '到店咨询',
    heat: item.heat || formatXhsHeat(score),
    heatScore: score,
    emoji: item.emoji || local.emoji || '💅',
    bg: item.bg || local.bg || '#FFF0F5',
    image: item.image || item.imageUrl || item.cover || local.image || '',
    detailed_image: item.detailed_image || item.detailedImage || local.detailed_image || '',
    rawStats: item.rawStats || null,
    crawlerStatus: item.crawlerStatus || '',
    crawlError: item.crawlError || '',
    trendSource: item.trendSource || '',
    sourceKind: item.sourceKind || '',
    platformName: item.platformName || (item.trendSource === 'bilibili-public' ? 'B站' : '平台'),
    platformUrl: item.platformUrl || item.bilibili || item.douyin || item.douyinUrl || item.awemeUrl || item.url || '',
    bilibili: item.bilibili || '',
    douyin: item.douyin || item.douyinUrl || item.awemeUrl || item.url || '',
    xhs: item.douyin || item.douyinUrl || item.awemeUrl || item.url || ''
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
        ${renderDouyinStats(item)}
        <div class="trend-foot">
          <span class="trend-heat">${item.heat}</span>
          <button class="mini-try" onclick="event.stopPropagation();setTryonStyle('${item.emoji}','${item.name}','${item.price}','${item.bg}','${item.image}');go('s-tryon')">试戴</button>
        </div>
        ${item.platformUrl
          ? `<a class="xhs-link" href="${item.platformUrl}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${item.platformName || '平台'}视频</a>`
          : `<span class="xhs-link disabled">待接入${item.platformName || '平台'}视频</span>`}
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
    note.textContent = `平台关键词热度参考 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)} · 可在 scripts/xhs-keyword-heat.js 调整分数`;
    return;
  }
  if (xhsTrendingState.source === 'public-crawler') {
    const fallbackCount = liveTrendingItems.filter(item => item.trendSource === 'local-fallback').length;
    note.textContent = fallbackCount
      ? `公开视频未暴露部分统计 · ${fallbackCount} 款使用本地热度参考 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`
      : `公开视频抓取 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`;
    return;
  }
  if (xhsTrendingState.source === 'public-discovery') {
    const realtimeCount = liveTrendingItems.filter(item => item.trendSource === 'douyin-public').length;
    const fallbackCount = liveTrendingItems.filter(item => item.trendSource === 'local-fallback').length;
    note.textContent = realtimeCount
      ? `自动发现公开视频 · ${realtimeCount} 款实时统计 · ${fallbackCount} 款本地参考 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`
      : `已尝试自动搜索视频 · 暂未读取到公开视频统计 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`;
    return;
  }
  if (xhsTrendingState.source === 'bilibili-live') {
    const realtimeCount = liveTrendingItems.filter(item => item.trendSource === 'bilibili-public').length;
    const fallbackCount = liveTrendingItems.filter(item => item.trendSource === 'local-fallback').length;
    note.textContent = `B站公开视频实时统计 · ${realtimeCount} 款实时 · ${fallbackCount} 款本地参考 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`;
    return;
  }
  if (xhsTrendingState.source === 'local-fallback') {
    note.textContent = `未接入公开视频 · 使用本地热度参考 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`;
    return;
  }
  note.textContent = `平台授权数据 · 更新于 ${formatUpdatedAt(xhsTrendingState.updatedAt)}`;
}

function paintTrendingHome() {
  const grid = document.getElementById('trend-grid');
  if (!grid) return;
  updateTrendNote();
  if (xhsTrendingState.status === 'loading') {
    grid.innerHTML = renderTrendMessage('正在同步平台热度', '连接公开视频或授权数据源后会自动按流量排序。');
    if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
    if (document.getElementById('s-ops')?.classList.contains('active') && typeof renderOpsDashboard === 'function') renderOpsDashboard();
    return;
  }
  if (xhsTrendingState.status !== 'ready') {
    grid.innerHTML = renderTrendMessage('未接入平台实时数据源', xhsTrendingState.message);
    if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
    if (document.getElementById('s-ops')?.classList.contains('active') && typeof renderOpsDashboard === 'function') renderOpsDashboard();
    return;
  }
  grid.innerHTML = renderTrendingCards(liveTrendingItems, 4);
  if (typeof renderOpsEntrySummary === 'function') renderOpsEntrySummary();
  if (document.getElementById('s-ops')?.classList.contains('active') && typeof renderOpsDashboard === 'function') renderOpsDashboard();
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
        message: '请在 scripts/xhs-config.js 填入你自己的平台授权数据接口，或在 backend/bilibili_sources.json 添加公开视频链接。',
        updatedAt: ''
      };
    }
    paintTrendingHome();
    if (currentFilter === '热门') renderGallery('热门');
    return;
  }

  xhsTrendingState = {
    status: 'loading',
    message: '正在获取平台实时热度...',
    updatedAt: ''
  };
  paintTrendingHome();

  try {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const errorPayload = await response.json();
        message = errorPayload.detail || errorPayload.message || message;
      } catch (e) {}
      throw new Error(message);
    }
    const payload = await response.json();
    liveTrendingItems = normalizeXhsTrendingPayload(payload);
      xhsTrendingState = {
        status: liveTrendingItems.length ? 'ready' : 'empty',
        message: payload.message || (liveTrendingItems.length ? '' : '实时接口已连接，但暂时没有返回美甲热门数据。'),
        updatedAt: payload.updatedAt || new Date().toISOString(),
        source: payload.source || 'official'
      };
  } catch (error) {
    liveTrendingItems = [];
    xhsTrendingState = {
      status: 'error',
      message: `平台实时数据获取失败：${error.message}`,
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
    const txt = chip.textContent.trim();
    // 兼容带 emoji 前缀的 chip（如 "✨ 我的灵感"），用 includes 而非完全相等
    chip.classList.toggle('on', !!filter && (txt === filter || txt.includes(filter)));
  });
}
