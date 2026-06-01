/* ══════════════════════════════════
   小红书实时数据配置
══════════════════════════════════ */
const XHS_TRENDING_CONFIG = {
  // 填入你自己的后端接口，例如：'/api/xhs/trending-nails'
  // 前端不会直接保存小红书 app-key / secret，避免泄露。
  endpoint: '',
  // 学生原型模式：没有官方接口时，用 scripts/xhs-keyword-heat.js 的关键词热度表生成热门榜。
  keywordFallback: true,
  refreshMs: 5 * 60 * 1000
};
