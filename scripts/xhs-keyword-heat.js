/* Douyin keyword heat table for student prototype fallback.

   This is not an official real-time Douyin API. It is a manual keyword model
   for demos when public video URLs or an authorized data API are not available.
*/
const XHS_KEYWORD_HEAT_UPDATED_AT = '2026-06-02';

function douyinKeywordUrl(keyword) {
  return `https://www.douyin.com/search/${encodeURIComponent(keyword)}`;
}

const XHS_KEYWORD_HEAT = [
  { keyword: '法式美甲', score: 98000, label: '高热', douyin: douyinKeywordUrl('法式美甲'), xhs: douyinKeywordUrl('法式美甲') },
  { keyword: '裸粉美甲', score: 92000, label: '高热', douyin: douyinKeywordUrl('裸粉美甲'), xhs: douyinKeywordUrl('裸粉美甲') },
  { keyword: '显白美甲', score: 88000, label: '高热', douyin: douyinKeywordUrl('显白美甲'), xhs: douyinKeywordUrl('显白美甲') },
  { keyword: '春夏美甲', score: 83000, label: '升温', douyin: douyinKeywordUrl('春夏美甲'), xhs: douyinKeywordUrl('春夏美甲') },
  { keyword: '小花美甲', score: 79000, label: '升温', douyin: douyinKeywordUrl('小花美甲'), xhs: douyinKeywordUrl('小花美甲') },
  { keyword: '玫瑰美甲', score: 76000, label: '升温', douyin: douyinKeywordUrl('玫瑰美甲'), xhs: douyinKeywordUrl('玫瑰美甲') },
  { keyword: '镜面美甲', score: 72000, label: '热门', douyin: douyinKeywordUrl('镜面美甲'), xhs: douyinKeywordUrl('镜面美甲') },
  { keyword: '玫瑰金美甲', score: 69000, label: '热门', douyin: douyinKeywordUrl('玫瑰金美甲'), xhs: douyinKeywordUrl('玫瑰金美甲') },
  { keyword: '通勤美甲', score: 64000, label: '稳定', douyin: douyinKeywordUrl('通勤美甲'), xhs: douyinKeywordUrl('通勤美甲') },
  { keyword: '日系美甲', score: 61000, label: '稳定', douyin: douyinKeywordUrl('日系美甲'), xhs: douyinKeywordUrl('日系美甲') },
  { keyword: '韩系美甲', score: 59000, label: '稳定', douyin: douyinKeywordUrl('韩系美甲'), xhs: douyinKeywordUrl('韩系美甲') },
  { keyword: '钻饰美甲', score: 56000, label: '热门', douyin: douyinKeywordUrl('钻饰美甲'), xhs: douyinKeywordUrl('钻饰美甲') },
  { keyword: '星星美甲', score: 52000, label: '热门', douyin: douyinKeywordUrl('星星美甲'), xhs: douyinKeywordUrl('星星美甲') },
  { keyword: '奶牛美甲', score: 47000, label: '小众热', douyin: douyinKeywordUrl('奶牛美甲'), xhs: douyinKeywordUrl('奶牛美甲') },
  { keyword: '豹纹美甲', score: 43000, label: '小众热', douyin: douyinKeywordUrl('豹纹美甲'), xhs: douyinKeywordUrl('豹纹美甲') },
  { keyword: '黑色美甲', score: 41000, label: '稳定', douyin: douyinKeywordUrl('黑色美甲'), xhs: douyinKeywordUrl('黑色美甲') }
];

const XHS_STYLE_KEYWORDS = {
  // ── 旧内置款式 ──
  '法式星芒裸粉': ['法式美甲', '裸粉美甲', '星星美甲', '钻饰美甲', '显白美甲'],
  '玫瑰渐变碎花': ['玫瑰美甲', '小花美甲', '春夏美甲', '显白美甲'],
  '牛油果奶咖': ['显白美甲', '通勤美甲', '日系美甲'],
  '镜面玫瑰金': ['镜面美甲', '玫瑰金美甲', '韩系美甲'],
  '小雏菊格纹': ['小花美甲', '春夏美甲', '日系美甲'],
  '香槟宝石': ['钻饰美甲', '裸粉美甲', '韩系美甲'],
  '黑金花园': ['黑色美甲', '小花美甲', '韩系美甲'],
  '奶牛法式': ['奶牛美甲', '法式美甲', '通勤美甲'],
  '彩钻果冻': ['钻饰美甲', '春夏美甲', '韩系美甲'],
  '豹纹银闪': ['豹纹美甲', '钻饰美甲', '韩系美甲'],
  '冰透法式钻': ['法式美甲', '钻饰美甲', '显白美甲'],
  '黑星银河': ['黑色美甲', '星星美甲', '韩系美甲'],
  // ── 后端 25 款真实款式 ──
  '奶油裸粉':   ['裸粉美甲', '显白美甲', '通勤美甲', '日系美甲'],
  '橄榄法式':   ['法式美甲', '显白美甲', '通勤美甲'],
  '酒红黑钻':   ['钻饰美甲', '黑色美甲', '韩系美甲'],
  '银灰猫眼':   ['镜面美甲', '通勤美甲', '韩系美甲'],
  '奶白小花':   ['小花美甲', '春夏美甲', '显白美甲'],
  '蜜桃鎏金':   ['玫瑰金美甲', '春夏美甲', '钻饰美甲'],
  '银豹法式':   ['法式美甲', '豹纹美甲', '韩系美甲'],
  '黑钻渐变':   ['黑色美甲', '钻饰美甲', '韩系美甲'],
  '极光黑曜':   ['黑色美甲', '镜面美甲', '韩系美甲'],
  '珍珠裸粉':   ['裸粉美甲', '显白美甲', '通勤美甲'],
  '镜面裸杏':   ['镜面美甲', '裸粉美甲', '通勤美甲'],
  '冰透碎钻':   ['钻饰美甲', '显白美甲', '韩系美甲'],
  '月光珍珠':   ['裸粉美甲', '显白美甲', '通勤美甲'],
  '莓果宝石':   ['玫瑰美甲', '钻饰美甲', '春夏美甲'],
  '玫瑰花园':   ['玫瑰美甲', '小花美甲', '春夏美甲'],
  '奶白蝴蝶结': ['显白美甲', '春夏美甲', '日系美甲'],
  '樱桃酒红':   ['玫瑰美甲', '韩系美甲', '钻饰美甲'],
  '香槟碎金':   ['钻饰美甲', '玫瑰金美甲', '韩系美甲'],
  '银豹长甲':   ['豹纹美甲', '镜面美甲', '韩系美甲'],
  '可可裸棕':   ['裸粉美甲', '显白美甲', '通勤美甲'],
  '玫瑰镜面':   ['玫瑰美甲', '镜面美甲', '韩系美甲'],
  '裸杏贝母':   ['裸粉美甲', '显白美甲', '通勤美甲'],
  '银镜长甲':   ['镜面美甲', '通勤美甲', '韩系美甲'],
  '莓红花漾':   ['玫瑰美甲', '小花美甲', '春夏美甲'],
  '粉钻渐变':   ['钻饰美甲', '玫瑰金美甲', '韩系美甲'],
};
