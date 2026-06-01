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
let userProfile = {
  name: '小美同学',
  avatar: '小',
  bio: '美甲爱好者',
  tryonCount: 12,
  bookingCount: 3
};
let currentDetail = { emoji:'🌸', name:'樱花奶油', price:'¥199', bg:'#FFF0F5' };
let prevScreen = 's-home';
let currentFilter = '全部';
let tryonStyleInfo = { emoji:'🌸', name:'樱花奶油', price:'¥199', bg:'#FFF0F5' };

// 后端地址（与 try-on.js 的 API_BASE 一致）
const DESIGNS_API = 'http://localhost:8000/api/designs';

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
    if (STYLES[0] && typeof setTryonStyle === 'function') {
      const s = STYLES[0];
      setTryonStyle(s.emoji, s.name, s.price, s.bg, s.image);
    }
  } catch (e) {
    console.warn('[Designs] 后端加载失败，使用内置 12 款兜底:', e.message);
  }
}

