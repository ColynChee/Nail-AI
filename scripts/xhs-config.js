/* Platform trend configuration */
const DOUYIN_TRENDING_CONFIG = {
  // Backend endpoint. Keep API keys on the backend, never in the browser.
  endpoint: 'http://localhost:8000/api/bilibili/trending-nails',
  // Student prototype fallback: when live platform data is unavailable, backend returns local reference data.
  keywordFallback: false,
  refreshMs: 5 * 60 * 1000
};

// Backward-compatible alias for the existing app wiring.
const XHS_TRENDING_CONFIG = DOUYIN_TRENDING_CONFIG;
