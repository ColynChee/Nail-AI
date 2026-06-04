/* ══════════════════════════════════
   DETAIL
══════════════════════════════════ */
const DETAIL_PALETTES = {
  red: ['#B71C1C', '#D84343', '#F7A1A1', '#F6D6D6', '#7A1F1F'],
  pink: ['#FFB3C6', '#F7A8B8', '#E8A0BF', '#FFE0EA', '#C85A7A'],
  green: ['#506B3F', '#7E9B5D', '#BFD7A2', '#F0E8CC', '#2F3F2F'],
  blue: ['#4A6FA5', '#7DA3D8', '#D9E8FF', '#F5F0FF', '#243B63'],
  purple: ['#8E6FB0', '#B9A0D8', '#E5D8F5', '#F7E6F0', '#4F3A68'],
  black: ['#151515', '#36302C', '#B08A54', '#F3E3C3', '#7C6A57'],
  brown: ['#6B4F3A', '#A87955', '#D6B28E', '#EFE1CF', '#3B2A20'],
  white: ['#F8F3EC', '#FFFFFF', '#E6E1DA', '#C8BFB3', '#F6D8CC'],
  silver: ['#D8DCE2', '#F6F7F8', '#AEB7C2', '#7D8791', '#ECE4FF'],
  default: ['#FFB3C6', '#FFCBA4', '#C9B8E8', '#FFEAA7', '#B2F0E8']
};

function detailHash(text) {
  return Array.from(String(text || '')).reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
}

function detailNumber(design, fallbackName) {
  const raw = design?.id || fallbackName || '';
  const m = String(raw).match(/(\d+)/);
  return m ? parseInt(m[1], 10) : (detailHash(raw) % 25) + 1;
}

function formatMetric(num) {
  const n = Number(num) || 0;
  if (n >= 10000) return `${(n / 10000).toFixed(1)}w`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

function formatDetailPercent(value) {
  const pct = (Number(value) || 0) * 100;
  if (!pct) return '0%';
  if (pct < 1) return '<1%';
  return `${pct < 10 ? pct.toFixed(1) : Math.round(pct)}%`;
}

function parseTraffic(value) {
  if (typeof value === 'number') return value;
  const text = String(value || '').toLowerCase();
  const num = parseFloat(text.replace(/[^\d.]/g, ''));
  if (!Number.isFinite(num)) return 0;
  if (text.includes('w') || text.includes('万')) return num * 10000;
  if (text.includes('k')) return num * 1000;
  return num;
}

function findDetailDesign(name, designId) {
  if (designId) {
    const byId = STYLES.find(d => d.id === designId);
    if (byId) return byId;
  }
  return STYLES.find(d => d.name === name) || null;
}

function getTrendItems() {
  return typeof getLiveTrendingItems === 'function' ? getLiveTrendingItems() : [];
}

function findTrendItem(design, name, designId) {
  const items = getTrendItems();
  return items.find(item => item.id && item.id === (designId || design?.id))
    || items.find(item => item.name === name)
    || null;
}

function isRealtimeTrendItem(item) {
  return item?.trendSource === 'douyin-public' || item?.trendSource === 'bilibili-public';
}

function trendPlatformName(item) {
  return item?.platformName || (item?.trendSource === 'bilibili-public' ? 'B站' : '平台');
}

function inferPaletteKey(name, tags) {
  const text = `${name || ''} ${(tags || []).join(' ')}`;
  if (/红|莓|玫瑰|丝绒/.test(text)) return 'red';
  if (/粉|樱|桃|少女|珊瑚/.test(text)) return 'pink';
  if (/绿|橄榄|薄荷/.test(text)) return 'green';
  if (/蓝|海岛/.test(text)) return 'blue';
  if (/紫|晚霞|葡萄/.test(text)) return 'purple';
  if (/黑|金|墨/.test(text)) return 'black';
  if (/棕|咖啡|焦糖|琥珀|巧克力/.test(text)) return 'brown';
  if (/白|奶油|裸色|象牙|燕麦/.test(text)) return 'white';
  if (/银|镜面|极光|闪片/.test(text)) return 'silver';
  return 'default';
}

function buildDetailTags(design, trendItem, sub) {
  const tags = [];
  if (isRealtimeTrendItem(trendItem)) tags.push(`${trendPlatformName(trendItem)}实时视频`);
  else if (trendItem?.trendSource === 'local-fallback') tags.push('热度参考');
  if (design?.tags?.length) tags.push(...design.tags.slice(0, 2));
  if (sub) tags.push(...sub.split('·').map(s => s.trim()).filter(Boolean).slice(0, 2));
  return [...new Set(tags)].slice(0, 4);
}

function renderDetailTags(tags) {
  const box = document.getElementById('d-tags');
  if (!box) return;
  const classes = ['tag-pink', 'tag-orange', 'tag-purple'];
  box.innerHTML = tags.map((tag, i) => `<span class="tag ${classes[i % classes.length]}">${tag}</span>`).join('');
}

function renderDetailStats(design, trendItem, idx) {
  const isRealtime = isRealtimeTrendItem(trendItem);
  const heat = isRealtime ? trendItem.heatScore : parseTraffic(design?.heat || trendItem?.heat || 0);
  const rank = trendItem?.rank || design?.rank || idx;
  const rawStats = trendItem?.rawStats || {};
  const views = parseTraffic(rawStats.viewCount);
  const interactions = parseTraffic(rawStats.likeCount) +
    parseTraffic(rawStats.collectCount) +
    parseTraffic(rawStats.commentCount) +
    parseTraffic(rawStats.shareCount) +
    parseTraffic(rawStats.danmakuCount) +
    parseTraffic(rawStats.coinCount);
  const interactionRate = views ? interactions / views : 0;

  document.getElementById('d-stat-tryons').textContent = formatMetric(heat);
  document.getElementById('d-stat-tryons-lbl').textContent = isRealtime ? `${trendPlatformName(trendItem)}热度` : '本地热度';
  document.getElementById('d-stat-rate').textContent = isRealtime ? formatDetailPercent(interactionRate) : '待接入';
  document.getElementById('d-stat-rate-lbl').textContent = isRealtime ? '互动率' : '平台互动';
  document.getElementById('d-stat-rank').textContent = `#${rank}`;
  document.getElementById('d-stat-rank-lbl').textContent = isRealtime ? '实时排名' : '本地排名';
}

function renderDetailColors(design, name) {
  const tags = design?.tags || [];
  const palette = DETAIL_PALETTES[inferPaletteKey(name, tags)] || DETAIL_PALETTES.default;
  const row = document.getElementById('d-color-row');
  if (!row) return;
  row.innerHTML = palette.map((color, i) =>
    `<div class="c-dot ${i === 0 ? 'on' : ''}" style="background:${color}" onclick="pickColor(this)" title="${color}"></div>`
  ).join('');
}

function buildDetailDescription(design, name, trendItem, idx) {
  const tags = design?.tags || [];
  const text = `${name || ''} ${tags.join(' ')}`;
  const finish = /镜面|银|极光|闪/.test(text) ? '高光镜面' : /丝绒|雾|橄榄/.test(text) ? '柔雾质感' : /白|裸|奶|燕麦/.test(text) ? '干净奶油感' : /黑|棕|咖啡|琥珀/.test(text) ? '低饱和高级感' : '清透亮面';
  const scene = /通勤|白|裸|燕麦|象牙/.test(text) ? '通勤、面试、日常穿搭' : /红|玫瑰|莓|丝绒/.test(text) ? '约会、聚会、节日造型' : /绿|蓝|紫|极光/.test(text) ? '拍照、旅行、个性穿搭' : '日常、约会和轻正式场合';
  const skin = /绿|蓝|紫|黑/.test(text) ? '冷白、自然色、小麦色' : /棕|咖啡|橘|琥珀/.test(text) ? '暖白、自然色、健康小麦色' : '暖白、自然色、偏白肤色';
  const hand = idx % 3 === 0 ? '甲床偏短也能拉长比例' : idx % 3 === 1 ? '修长手型会更显精致' : '普通手型也比较友好';
  const source = isRealtimeTrendItem(trendItem)
    ? `关联${trendPlatformName(trendItem)}公开视频当前热度约 ${trendItem.heat}，适合放在热门推荐位。`
    : '当前未读取到公开视频实时统计，热度使用本地款式库参考值。';
  const time = 75 + (idx % 5) * 10;
  return `${name} 的重点是${finish}，整体风格偏${tags[0] || '百搭'}，不会过分抢眼，但近看有细节。适合${scene}。<br><br>适合肤色：${skin}。<br>适合手型：${hand}。<br><br>${source}<br>预计工期约 ${time} 分钟，建议提前预约。`;
}

function relatedPostsFor(design, trendItem) {
  const items = getTrendItems();
  const designTags = design?.tags || [];
  const exact = trendItem ? [trendItem] : [];
  const related = items.filter(item => item !== trendItem && (
    item.id === design?.id ||
    designTags.some(tag => (item.sub || '').includes(tag) || (item.name || '').includes(tag)) ||
    isRealtimeTrendItem(item)
  ));
  return [...exact, ...related].slice(0, 3);
}

function renderRelatedPosts(design, trendItem) {
  const box = document.getElementById('d-related-posts');
  if (!box) return;
  const posts = relatedPostsFor(design, trendItem);
  if (!posts.length) {
    box.innerHTML = '<div class="related-empty">还没有关联到公开视频。添加公开视频链接后，这里会显示实时热度与入口。</div>';
    return;
  }
  box.innerHTML = posts.map(post => {
    const source = isRealtimeTrendItem(post) ? '实时' : '参考';
    const platform = trendPlatformName(post);
    const title = post.name || design?.name || `${platform}视频`;
    const meta = post.crawlerStatus === 'ok'
      ? `公开视频 · ${post.heat || formatMetric(post.heatScore)}`
      : `${post.crawlerStatus === 'login_required' ? '需登录' : '公开统计隐藏'} · ${post.heat || '热度参考'}`;
    return `
      <a class="related-post-card" href="${post.platformUrl || post.bilibili || post.douyin || post.douyinUrl || post.xhs || '#'}" target="_blank" rel="noopener">
        <div class="related-post-mark">${platform === 'B站' ? 'B' : '抖'}</div>
        <div class="related-post-main">
          <div class="related-post-title">${title}</div>
          <div class="related-post-meta">${meta}</div>
        </div>
        <div class="related-post-score">${source}</div>
      </a>`;
  }).join('');
}

function goDetail(emoji, name, sub, price, bg, image, designId = null) {
  const design = findDetailDesign(name, designId);
  const trendItem = findTrendItem(design, name, designId);
  const idx = detailNumber(design, name);
  currentDetail = { emoji, name, price, bg, image, designId };
  prevScreen = document.querySelector('.screen.active').id;

  const detailImage = document.getElementById('d-image');
  const detailEmoji = document.getElementById('d-emoji');
  const displayImage = image || design?.detailed_image || design?.image || trendItem?.image || '';
  if (displayImage) {
    detailImage.src = displayImage;
    detailImage.alt = name;
    detailImage.classList.add('show');
  } else {
    detailImage.removeAttribute('src');
    detailImage.alt = '';
    detailImage.classList.remove('show');
    detailEmoji.textContent = emoji;
  }

  document.getElementById('d-name').textContent = design?.name || name;
  document.getElementById('d-price').textContent = design?.price || price;
  document.getElementById('detail-hero-bg').style.background = bg || design?.bg || 'var(--cream)';

  const tags = buildDetailTags(design, trendItem, sub);
  renderDetailTags(tags);
  renderDetailStats(design, trendItem, idx);
  renderDetailColors(design, name);
  renderRelatedPosts(design, trendItem);
  document.getElementById('d-desc').innerHTML = buildDetailDescription(design, design?.name || name, trendItem, idx);

  const detailedImgBox = document.getElementById('d-detailed-img-box');
  const detailedImg = document.getElementById('d-detailed-img');
  if (design && design.detailed_image) {
    detailedImg.src = design.detailed_image;
    detailedImgBox.style.display = 'block';
  } else {
    detailedImgBox.style.display = 'none';
  }

  const inWl = wishlist.find(w => w.name === name);
  const btn = document.getElementById('d-fav-btn');
  btn.classList.toggle('liked', !!inWl);
  go('s-detail');
}

function toggleDetailFav() {
  const btn = document.getElementById('d-fav-btn');
  btn.classList.toggle('liked');
  if (btn.classList.contains('liked')) {
    addToWishlist(currentDetail.emoji, currentDetail.name, currentDetail.price, currentDetail.bg, currentDetail.image);
    showToast('已添加到收藏 ♥');
  } else {
    wishlist = wishlist.filter(w => w.name !== currentDetail.name);
    saveWishlistState();
    updateProfileCounts();
    showToast('已移出收藏');
  }
}

function pickColor(dot) {
  document.querySelectorAll('.c-dot').forEach(d => d.classList.remove('on'));
  dot.classList.add('on');
}
