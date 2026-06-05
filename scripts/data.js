/* ══════════════════════════════════
   DATA
══════════════════════════════════ */
// STYLES 用 let：启动时会被 loadDesignsFromBackend() 替换为后端 /api/designs 的 25 个真实款式。
// 下面这 12 个是离线兜底（后端不可用时仍可浏览）。
let STYLES = [
  { emoji:'✨', name:'法式星芒裸粉', tags:['春夏','约会','法式'], bg:'#FFF0EB', price:'¥229', heat:'9.8k', rank:1, image:'款式图/2277d6f9d82264fa6a3c986373e5e44c2292083.webp' },
  { emoji:'🌹', name:'玫瑰渐变碎花', tags:['春夏','约会'], bg:'#FFF0F5', price:'¥219', heat:'8.6k', rank:2, image:'款式图/137aad1f6a36655ae395cf7dc57604642782680.webp' },
  { emoji:'🍵', name:'牛油果奶咖', tags:['通勤','秋冬','日系'], bg:'#F0FDF4', price:'¥189', heat:'7.4k', rank:3, image:'款式图/162afb52255bd908ba3ec418fd61824a2254875.webp' },
  { emoji:'💅', name:'镜面玫瑰金', tags:['韩系','约会'], bg:'#F5F0FF', price:'¥259', heat:'6.9k', rank:4, image:'款式图/5b985a1c661ae2e964286178e6c0b0f92258113.webp' },
  { emoji:'🌼', name:'小雏菊格纹', tags:['春夏','日系'], bg:'#FFF0F5', price:'¥199', heat:'5.8k', rank:5, image:'款式图/1248ad42d355b98257e5fbcdf90efc552138079.webp' },
  { emoji:'💎', name:'香槟宝石', tags:['秋冬','约会','韩系'], bg:'#F7F3F0', price:'¥269', heat:'5.2k', rank:6, image:'款式图/5fad21e6d38656170bf726ff3973a4501918338.webp' },
  { emoji:'🌿', name:'黑金花园', tags:['秋冬','韩系'], bg:'#F0FDF4', price:'¥239', heat:'4.8k', rank:7, image:'款式图/43cc4ced977a3dd271f60ee2f05607772681747.webp' },
  { emoji:'🤍', name:'奶牛法式', tags:['法式','通勤'], bg:'#F7F3F0', price:'¥169', heat:'4.4k', rank:8, image:'款式图/3c0d090e20f0cb56f70fcb56c54dd6582416974.webp' },
  { emoji:'💠', name:'彩钻果冻', tags:['春夏','韩系'], bg:'#FFF5F5', price:'¥229', heat:'3.9k', rank:9, image:'款式图/5591229138c4e7e1d183b59be442d9dc2267735.webp' },
  { emoji:'🐆', name:'豹纹银闪', tags:['秋冬','约会'], bg:'#F5F0FF', price:'¥249', heat:'3.5k', rank:10, image:'款式图/2ac2d01a9bc78320edbe2b545b485b4a2132292.webp' },
  { emoji:'🤍', name:'冰透法式钻', tags:['法式','通勤'], bg:'#EFF6FF', price:'¥219', heat:'3.1k', rank:11, image:'款式图/682c173ae3a95d0b838655e8337b30d72213857.webp' },
  { emoji:'⭐', name:'黑星银河', tags:['秋冬','韩系'], bg:'#F5F0FF', price:'¥239', heat:'2.8k', rank:12, image:'款式图/69614397f0ecb559b98cb46a5a46f3b32642714.webp' },
];

let wishlist = [];
let bookings = [];
let tryonHistory = [];
let imageTryonHistory = [];
let userProfile = {
  name: '小美同学',
  avatar: '小',
  age: 24,
  skinColorCode: '#F5C6A0',
  skinToneLabel: '自然色',
  skinToneSource: 'preset',
  bio: '美甲爱好者',
  tryonCount: 0,
  bookingCount: 0
};
let currentDetail = { emoji:'🌸', name:'樱花奶油', price:'¥199', bg:'#FFF0F5' };
let prevScreen = 's-home';
let currentFilter = '全部';
let tryonStyleInfo = { emoji:'🌸', name:'樱花奶油', price:'¥199', bg:'#FFF0F5' };

// 后端地址（与 try-on.js 的 API_BASE 一致）
const DESIGNS_API = 'http://localhost:8000/api/designs';

const DEFAULT_SKIN_COLOR = '#F5C6A0';

function normalizeHexColor(value) {
  if (typeof value !== 'string') return '';
  let hex = value.trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(hex)) {
    hex = hex.split('').map(ch => ch + ch).join('');
  }
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return '';
  return `#${hex.toUpperCase()}`;
}

function hexToRgb(hex) {
  const normalized = normalizeHexColor(hex);
  if (!normalized) return null;
  const value = normalized.slice(1);
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function rgbToHsl(r, g, b) {
  r /= 255;
  g /= 255;
  b /= 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;

  if (max === min) {
    return { h: 0, s: 0, l: l * 100 };
  }

  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;

  switch (max) {
    case r:
      h = (g - b) / d + (g < b ? 6 : 0);
      break;
    case g:
      h = (b - r) / d + 2;
      break;
    default:
      h = (r - g) / d + 4;
      break;
  }

  return {
    h: Math.round((h / 6) * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
  };
}

function hueDistance(a, b) {
  const diff = Math.abs(a - b) % 360;
  return Math.min(diff, 360 - diff);
}

function getSkinToneProfile(hex) {
  const normalized = normalizeHexColor(hex) || DEFAULT_SKIN_COLOR;
  const rgb = hexToRgb(normalized);
  if (!rgb) {
    return {
      code: DEFAULT_SKIN_COLOR,
      label: '自然色',
      undertone: 'neutral',
      hsl: { h: 28, s: 65, l: 66 },
    };
  }

  const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
  const warm = hsl.h >= 18 && hsl.h <= 62;
  const cool = hsl.h >= 185 && hsl.h <= 290;

  let label = '自然色';
  if (hsl.l >= 78) {
    label = cool ? '冷白色' : '暖白色';
  } else if (hsl.l >= 62) {
    label = warm ? '自然色' : '冷白色';
  } else if (hsl.l >= 48) {
    label = warm ? '小麦色' : '自然色';
  } else {
    label = '健康棕';
  }

  return {
    code: normalized,
    label,
    undertone: warm ? 'warm' : cool ? 'cool' : 'neutral',
    hsl,
  };
}

function getStyleRecommendationText(style) {
  const tags = Array.isArray(style.tags) ? style.tags.filter(Boolean) : [];
  return tags.slice(0, 2).join(' · ') || '百搭推荐';
}

function buildSkinRecommendationReason(style, skinProfile) {
  const text = `${style.name || ''} ${(style.tags || []).join(' ')} ${(style.price || '')}`;
  const label = skinProfile?.label || '自然色';

  if (label === '暖白色') {
    if (/(裸|奶|雾|粉|法式|冰|透)/.test(text)) return '浅调肤色更显净透';
    return '轻柔色调更提气色';
  }
  if (label === '自然色') {
    if (/(奶|咖|玫瑰|豆沙|香槟|法式|果冻)/.test(text)) return '自然肤色百搭耐看';
    return '温润配色更显协调';
  }
  if (label === '小麦色') {
    if (/(亮|钻|银|金|果冻|宝石|镜面|闪)/.test(text)) return '高亮元素更显肤色干净';
    return '饱和度更高的款式更出彩';
  }
  if (/(亮|钻|银|金|果冻|宝石|镜面|闪|黑|深)/.test(text)) return '深浅对比更容易显白';
  return '稳重配色更适合当前肤色';
}

function scoreStyleForSkin(style, skinHex) {
  const skin = getSkinToneProfile(skinHex);
  const text = `${style.name || ''} ${(style.tags || []).join(' ')} ${(style.price || '')}`;
  const lower = text.toLowerCase();
  let score = 0;

  if (skin.hsl.l >= 76) {
    if (/(裸|奶|雾|粉|法式|冰|透)/.test(text)) score += 18;
    if (/(钻|金|银|星|闪)/.test(text)) score += 8;
  } else if (skin.hsl.l >= 58) {
    if (/(奶|咖|玫瑰|豆沙|香槟|法式|果冻)/.test(text)) score += 18;
    if (/(银|冰|钻|星|闪|镜面)/.test(text)) score += 12;
  } else {
    if (/(亮|钻|银|金|果冻|宝石|镜面|闪)/.test(text)) score += 22;
    if (/(黑|深|豹|星)/.test(text)) score += 8;
  }

  if (skin.undertone === 'warm') {
    if (/(橘|金|奶|咖|裸|杏|玫|珊瑚)/.test(text)) score += 14;
    if (/(蓝|紫|冰|银)/.test(text)) score += 4;
  } else if (skin.undertone === 'cool') {
    if (/(粉|紫|银|冰|蓝|白|珍珠|星)/.test(text)) score += 14;
    if (/(橘|黄|金|咖)/.test(text)) score += 4;
  } else {
    if (/(粉|奶|法式|钻|香槟|果冻)/.test(text)) score += 8;
  }

  const bgRgb = hexToRgb(style.bg);
  if (bgRgb) {
    const bgHsl = rgbToHsl(bgRgb.r, bgRgb.g, bgRgb.b);
    const lightnessGap = Math.abs(bgHsl.l - skin.hsl.l);
    score += Math.min(12, lightnessGap / 4);

    const hueGap = hueDistance(bgHsl.h, skin.hsl.h);
    if (skin.undertone === 'warm' && hueGap < 50) score += 6;
    if (skin.undertone === 'cool' && hueGap > 20 && hueGap < 150) score += 6;
  }

  if (/法式|通勤/.test(lower)) score += 2;

  return Math.round(score);
}

function getRecommendedStyles() {
  const skinHex = normalizeHexColor(userProfile.skinColorCode) || DEFAULT_SKIN_COLOR;
  const skinProfile = getSkinToneProfile(skinHex);
  return [...STYLES]
    .map((style, index) => ({
      ...style,
      recReason: buildSkinRecommendationReason(style, skinProfile),
      recScore: scoreStyleForSkin(style, skinHex),
      recIndex: index,
    }))
    .sort((a, b) => b.recScore - a.recScore || a.recIndex - b.recIndex)
    .slice(0, 3);
}

function renderHomeRecommendations() {
  const list = document.getElementById('home-recommend-list');
  if (!list) return;

  const note = document.getElementById('home-recommend-note');
  const skinHex = normalizeHexColor(userProfile.skinColorCode) || DEFAULT_SKIN_COLOR;
  const skinProfile = getSkinToneProfile(skinHex);
  const recommended = getRecommendedStyles();

  if (note) {
    note.textContent = `已根据你的肤色 ${skinProfile.code} · ${skinProfile.label} 推荐`;
  }

  if (!recommended.length) {
    list.innerHTML = `
      <div class="data-empty" style="grid-column:1/-1">
        <div class="data-empty-title">暂无可推荐款式</div>
        <div class="data-empty-text">请稍后再试。</div>
      </div>`;
    return;
  }

  list.innerHTML = recommended.map((style, index) => `
    <div class="style-row card-press" onclick="goDetail('${style.emoji}','${style.name}','${getStyleRecommendationText(style)}','${style.price}','${style.bg}','${style.image || ''}','${style.id || ''}')">
      <div class="style-thumb" style="background:${style.bg}">${style.image ? `<img src="${style.image}" alt="${style.name}" style="width:100%;height:100%;object-fit:cover;border-radius:14px">` : style.emoji}</div>
      <div class="style-info">
        <div class="style-name">${style.name}</div>
        <div class="style-sub">${style.recReason || '肤色匹配推荐'}</div>
        <div class="style-tags">
          ${(style.tags || []).slice(0, 2).map(tag => `<span class="tag tag-orange">${tag}</span>`).join('')}
          ${index === 0 ? '<span class="tag tag-pink">最匹配</span>' : ''}
        </div>
      </div>
      <div class="style-right">
        <div class="style-price">${style.price}</div>
        <button class="heart-btn" onclick="event.stopPropagation();toggleHeart(this,'${style.name}','${style.emoji}','${style.price}','${style.bg}','${style.image || ''}')">
          <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        </button>
      </div>
    </div>`).join('');
}

/**
 * 启动时从后端拉取 25 个真实款式替换 STYLES（单一数据源）。
 * 成功则刷新款式库与默认试戴款式；失败则保留内置 12 个兜底。
 */
async function loadDesignsFromBackend() {
  try {
    const res = await fetch(DESIGNS_API);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const list = (data.designs || []).filter(d => d.image);
    if (!list.length) throw new Error('空款式列表');

    // 映射成前端 STYLES 结构
    STYLES = list.map((d, i) => ({
      id: d.id,
      emoji: d.emoji || '💅',
      name: d.name || `款式${i + 1}`,
      tags: (d.tags && d.tags.length) ? d.tags : ['日常', '百搭'],
      bg: d.bg || '#FFF4F0',
      price: d.price || '—',
      heat: d.heat || '—',
      rank: d.rank || (i + 1),
      image: d.image,           // 形如 "款式图/xxx.webp"，前端从根目录可直接访问
      detailed_image: d.detailed_image,
    }));

    console.log(`[Designs] 已从后端加载 ${STYLES.length} 个款式`);
    // 刷新依赖 STYLES 的视图
    if (typeof renderGallery === 'function') renderGallery(currentFilter || '全部');
    if (typeof renderHomeRecommendations === 'function') renderHomeRecommendations();
    if (STYLES[0] && typeof setTryonStyle === 'function') {
      const s = STYLES[0];
      setTryonStyle(s.emoji, s.name, s.price, s.bg, s.image);
    }
  } catch (e) {
    console.warn('[Designs] 后端加载失败，使用内置 12 款兜底:', e.message);
    if (typeof renderHomeRecommendations === 'function') renderHomeRecommendations();
  }
}
