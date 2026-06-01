/* ══════════════════════════════════
   小红书关键词热度表（学生版）

   使用方法：
   1. 去小红书搜索美甲关键词，例如“法式美甲”“裸粉美甲”。
   2. 根据你观察到的笔记数量、点赞收藏、近期内容多少，调整 score。
   3. 分数越高，今日热门排序越靠前。

   这不是小红书官方实时接口；它是适合学生作品集/课堂演示的关键词热度模型。
══════════════════════════════════ */
const XHS_KEYWORD_HEAT_UPDATED_AT = '2026-05-24';

const XHS_KEYWORD_HEAT = [
  { keyword: '法式美甲', score: 98000, label: '高热', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E6%B3%95%E5%BC%8F%E7%BE%8E%E7%94%B2' },
  { keyword: '裸粉美甲', score: 92000, label: '高热', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E8%A3%B8%E7%B2%89%E7%BE%8E%E7%94%B2' },
  { keyword: '显白美甲', score: 88000, label: '高热', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E6%98%BE%E7%99%BD%E7%BE%8E%E7%94%B2' },
  { keyword: '春夏美甲', score: 83000, label: '升温', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E6%98%A5%E5%A4%8F%E7%BE%8E%E7%94%B2' },
  { keyword: '小花美甲', score: 79000, label: '升温', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E5%B0%8F%E8%8A%B1%E7%BE%8E%E7%94%B2' },
  { keyword: '玫瑰美甲', score: 76000, label: '升温', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E7%8E%AB%E7%91%B0%E7%BE%8E%E7%94%B2' },
  { keyword: '镜面美甲', score: 72000, label: '热门', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E9%95%9C%E9%9D%A2%E7%BE%8E%E7%94%B2' },
  { keyword: '玫瑰金美甲', score: 69000, label: '热门', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E7%8E%AB%E7%91%B0%E9%87%91%E7%BE%8E%E7%94%B2' },
  { keyword: '通勤美甲', score: 64000, label: '稳定', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E9%80%9A%E5%8B%A4%E7%BE%8E%E7%94%B2' },
  { keyword: '日系美甲', score: 61000, label: '稳定', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E6%97%A5%E7%B3%BB%E7%BE%8E%E7%94%B2' },
  { keyword: '韩系美甲', score: 59000, label: '稳定', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E9%9F%A9%E7%B3%BB%E7%BE%8E%E7%94%B2' },
  { keyword: '钻饰美甲', score: 56000, label: '热门', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E9%92%BB%E9%A5%B0%E7%BE%8E%E7%94%B2' },
  { keyword: '星星美甲', score: 52000, label: '热门', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E6%98%9F%E6%98%9F%E7%BE%8E%E7%94%B2' },
  { keyword: '奶牛美甲', score: 47000, label: '小众热', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E5%A5%B6%E7%89%9B%E7%BE%8E%E7%94%B2' },
  { keyword: '豹纹美甲', score: 43000, label: '小众热', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E8%B1%B9%E7%BA%B9%E7%BE%8E%E7%94%B2' },
  { keyword: '黑色美甲', score: 41000, label: '稳定', xhs: 'https://www.xiaohongshu.com/search_result?keyword=%E9%BB%91%E8%89%B2%E7%BE%8E%E7%94%B2' }
];

const XHS_STYLE_KEYWORDS = {
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
  '黑星银河': ['黑色美甲', '星星美甲', '韩系美甲']
};
