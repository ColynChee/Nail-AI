/* ══════════════════════════════════
   INTELLIGENT OPERATIONS DASHBOARD
══════════════════════════════════ */
let opsLastItems = [];
let opsAssistantSignature = '';
let opsAssistantRequestId = 0;
let opsTrendChart = null;
const OPS_API_BASE = 'http://localhost:8000';

function opsNumber(value) {
  if (typeof toTrafficNumber === 'function') return toTrafficNumber(value);
  if (typeof value === 'number') return value;
  const text = String(value || '').trim().toLowerCase();
  const num = Number.parseFloat(text.replace(/[^\d.]/g, ''));
  if (!Number.isFinite(num)) return 0;
  if (text.includes('w') || text.includes('万')) return num * 10000;
  if (text.includes('k')) return num * 1000;
  return num;
}

function opsMetric(value) {
  const num = opsNumber(value);
  if (!num) return '0';
  if (num >= 10000) return `${(num / 10000).toFixed(1)}w`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
  return `${Math.round(num)}`;
}

function opsPercent(value) {
  const num = Number(value) || 0;
  if (!num) return '0%';
  return `${Math.max(0, Math.min(99, num * 100)).toFixed(1)}%`;
}

function opsClamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function opsEscapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function opsKey(item) {
  return String(item?.id || item?.name || '');
}

function opsFindLocalDesign(item) {
  if (typeof STYLES === 'undefined' || !Array.isArray(STYLES)) return null;
  const id = item?.id || item?.design_id || item?.designId;
  if (id) {
    const byId = STYLES.find(style => style.id === id);
    if (byId) return byId;
  }
  const name = item?.name || item?.localName || item?.keyword || '';
  return STYLES.find(style => (
    style.name === name ||
    String(name).includes(style.name) ||
    String(style.name).includes(name)
  )) || null;
}

function opsPlatformName(item) {
  const raw = String(item?.platformName || '');
  if (item?.trendSource === 'bilibili-public' || item?.bilibili || raw.toLowerCase().includes('bilibili') || raw.includes('B')) return 'B站';
  if (item?.trendSource === 'douyin-public' || item?.douyin || raw.includes('抖')) return '抖音';
  if (item?.trendSource === 'rednote-public' || item?.xhs || raw.includes('小红书')) return '小红书';
  if (item?.trendSource === 'local-fallback') return '本地参考';
  return raw || '平台';
}

function opsFormatTime(value) {
  if (!value) return '待同步';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function opsStyleLine(item) {
  const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean).slice(0, 2) : [];
  if (tags.length) return tags.join(' · ');
  return item.sub || '款式库';
}

function opsStats(item) {
  const raw = item?.rawStats || {};
  const view = opsNumber(raw.viewCount || item?.viewCount || item?.views || item?.playCount);
  const like = opsNumber(raw.likeCount || item?.likeCount || item?.likes);
  const collect = opsNumber(raw.collectCount || item?.collectCount || item?.favoriteCount || item?.favorites);
  const comment = opsNumber(raw.commentCount || item?.commentCount || item?.comments);
  const share = opsNumber(raw.shareCount || item?.shareCount || item?.shares);
  const danmaku = opsNumber(raw.danmakuCount || item?.danmakuCount);
  const coin = opsNumber(raw.coinCount || item?.coinCount);
  const heat = opsNumber(item?.heatScore) || view + like * 6 + collect * 8 + comment * 10 + share * 12 + danmaku * 3 + coin * 6 || opsNumber(item?.heat);
  const interactions = like + collect + comment + share + danmaku + coin;
  const intent = like + collect * 1.4 + comment * 1.8 + share * 2 + danmaku * 0.5 + coin * 0.7;
  const engagementRate = view ? interactions / view : 0;
  const collectRate = view ? collect / view : 0;
  return { view, like, collect, comment, share, danmaku, coin, heat, interactions, intent, engagementRate, collectRate };
}

function opsNormalizeItem(item, index) {
  const local = opsFindLocalDesign(item) || {};
  const stats = opsStats(item);
  return {
    ...local,
    ...item,
    id: item.id || item.design_id || item.designId || local.id || `ops_${index + 1}`,
    rank: item.rank || index + 1,
    name: item.name || local.name || `款式 ${index + 1}`,
    sub: item.sub || local.sub || opsStyleLine(local),
    price: item.price || local.price || '到店咨询',
    bg: item.bg || local.bg || '#FFF0F5',
    emoji: item.emoji || local.emoji || '💅',
    image: item.image || local.image || '',
    detailed_image: item.detailed_image || local.detailed_image || '',
    tags: Array.isArray(local.tags) ? local.tags : (Array.isArray(item.tags) ? item.tags : []),
    heatScore: stats.heat,
    platformName: opsPlatformName(item),
    platformUrl: item.platformUrl || item.bilibili || item.douyin || item.xhs || '',
    trendSource: item.trendSource || 'local-fallback'
  };
}

function getOpsItems() {
  const live = typeof getLiveTrendingItems === 'function' ? getLiveTrendingItems() : [];
  const base = live.length
    ? live
    : (Array.isArray(STYLES) ? STYLES.map((style, index) => ({
        ...style,
        rank: index + 1,
        heatScore: opsNumber(style.heat),
        rawStats: {},
        platformName: '本地参考',
        platformUrl: '',
        trendSource: 'local-fallback',
        crawlerStatus: 'local'
      })) : []);

  return base
    .map(opsNormalizeItem)
    .filter(item => item.name)
    .sort((a, b) => opsStats(b).heat - opsStats(a).heat)
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function opsSummary(items) {
  const state = typeof getLiveTrendingState === 'function' ? getLiveTrendingState() : {};
  const styleTotal = Array.isArray(STYLES) && STYLES.length ? STYLES.length : items.length;
  const totals = items.reduce((acc, item) => {
    const stats = opsStats(item);
    acc.view += stats.view;
    acc.like += stats.like;
    acc.collect += stats.collect;
    acc.comment += stats.comment;
    acc.share += stats.share;
    acc.danmaku += stats.danmaku;
    acc.coin += stats.coin;
    acc.heat += stats.heat;
    acc.intent += stats.intent;
    return acc;
  }, { view: 0, like: 0, collect: 0, comment: 0, share: 0, danmaku: 0, coin: 0, heat: 0, intent: 0 });
  const liveCount = items.filter(item => item.trendSource === 'bilibili-public' || item.trendSource === 'douyin-public').length;
  const fallbackCount = items.filter(item => item.trendSource === 'local-fallback').length;
  const top = items[0] || null;
  const topStats = top ? opsStats(top) : null;
  const liveRatio = styleTotal ? liveCount / styleTotal : 0;
  const viewBoost = Math.min(8, Math.log10(totals.view + 1) * 1.25);
  const intentBoost = Math.min(8, totals.intent / 50000);
  const engagementBoost = topStats ? Math.min(10, topStats.engagementRate * 200) : 0;
  const score = items.length
    ? Math.round(opsClamp(58 + liveRatio * 18 + viewBoost + intentBoost + engagementBoost, 60, 96))
    : 0;
  return {
    state,
    styleTotal,
    liveCount,
    fallbackCount,
    top,
    totals,
    score,
    averageView: items.length ? totals.view / items.length : 0,
    averageHeat: items.length ? totals.heat / items.length : 0
  };
}

function opsSourceText(summary) {
  const state = summary.state || {};
  if (state.status === 'loading') return '正在同步平台数据';
  if (state.source === 'bilibili-live') return 'B站公开视频实时统计';
  if (summary.liveCount) return '平台公开视频实时统计';
  if (state.status === 'error') return '实时接口失败，当前使用本地参考';
  return '本地款式热度参考';
}

function opsActionFor(item, index) {
  const stats = opsStats(item);
  const tags = Array.isArray(item.tags) ? item.tags.join(' ') : '';
  if (item.trendSource === 'local-fallback') {
    return { label: '补数据', pill: 'watch', desc: '补充公开视频或授权 API，避免只靠本地热度判断。' };
  }
  if (index === 0) {
    return { label: '主推', pill: 'hot', desc: '首页热门首位展示，并同步为 AI 试戴默认推荐款。' };
  }
  if (index < 3) {
    return { label: '联动', pill: 'hot', desc: '与主推款组成同风格组合，详情页放相关视频入口。' };
  }
  if (stats.collectRate > 0.015 || stats.collect > stats.like * 0.35) {
    return { label: '转化', pill: 'fit', desc: '收藏意向较强，优先生成试戴素材和色卡卖点。' };
  }
  if (/春夏|夏|亮|粉|蓝|绿/.test(tags + item.name)) {
    return { label: '上新', pill: 'fit', desc: '适合做季节主题专题，搭配轻量促销话术。' };
  }
  if (stats.engagementRate < 0.015 && stats.view > 0) {
    return { label: '优化', pill: 'watch', desc: '曝光有了但互动偏弱，调整标题、封面和试戴对比图。' };
  }
  return { label: '观察', pill: 'watch', desc: '保持在款式库推荐位，等待下一轮热度变化。' };
}

function opsRiskFor(item, summary) {
  const stats = opsStats(item);
  if (item.trendSource === 'local-fallback') {
    return { issue: '数据缺口', action: '补充 B站公开视频链接，或改接授权平台 API。', score: 100 };
  }
  if (!item.platformUrl) {
    return { issue: '缺少内容入口', action: '补充平台视频链接，让详情页能承接用户验证。', score: 82 };
  }
  if (summary.averageView && stats.view < summary.averageView * 0.45) {
    return { issue: '曝光偏低', action: '下调首页权重，改用同色系高热款带动。', score: 72 };
  }
  if (stats.engagementRate < 0.012 && stats.view > 0) {
    return { issue: '互动偏弱', action: '重做封面和前三秒卖点，突出上手效果。', score: 64 };
  }
  if (stats.collectRate < 0.004 && item.rank > 10) {
    return { issue: '收藏意愿弱', action: '补充肤色适配说明，减少用户决策成本。', score: 54 };
  }
  return { issue: '表达可加强', action: '补充试戴前后对比，提升款式理解速度。', score: 36 };
}

function opsInferTrendLabels(item) {
  const labels = new Set(Array.isArray(item.tags) ? item.tags.filter(Boolean) : []);
  const text = `${item.name || ''} ${item.sub || ''}`.toLowerCase();
  const rules = [
    ['裸色', /裸|奶油|燕麦|象牙|nude/],
    ['法式', /法式|french/],
    ['猫眼', /猫眼/],
    ['秋冬', /秋冬|棕|咖|黑|丝绒|琥珀|橄榄/],
    ['春夏', /春夏|粉|蓝|绿|橘|珊瑚|海岛|樱花/],
    ['闪耀', /闪|银|镜面|极光|钻|珠/],
    ['通勤', /通勤|简约|白|日常/],
    ['甜美', /甜|粉|桃|玫瑰|少女/],
    ['酷感', /黑|墨|金属|漆/]
  ];
  rules.forEach(([label, regex]) => {
    if (regex.test(text)) labels.add(label);
  });
  if (!labels.size) labels.add('百搭');
  return [...labels].slice(0, 4);
}

function opsTrendBuckets(items) {
  const buckets = new Map();
  items.forEach(item => {
    const stats = opsStats(item);
    opsInferTrendLabels(item).forEach(label => {
      const row = buckets.get(label) || {
        label,
        heat: 0,
        view: 0,
        intent: 0,
        engagement: 0,
        count: 0,
        examples: []
      };
      row.heat += stats.heat;
      row.view += stats.view;
      row.intent += stats.intent;
      row.engagement += stats.engagementRate;
      row.count += 1;
      row.examples.push(item);
      buckets.set(label, row);
    });
  });
  return [...buckets.values()]
    .map(row => ({
      ...row,
      avgEngagement: row.count ? row.engagement / row.count : 0,
      examples: row.examples.sort((a, b) => opsStats(b).heat - opsStats(a).heat).slice(0, 2)
    }))
    .sort((a, b) => b.heat - a.heat);
}

function opsTrendSignal(bucket, summary) {
  const heatShare = summary.totals.heat ? bucket.heat / summary.totals.heat : 0;
  if (heatShare >= 0.32 || bucket.avgEngagement >= 0.08) return '强上升';
  if (heatShare >= 0.18 || bucket.avgEngagement >= 0.045) return '稳定增长';
  return '观察中';
}

function renderOpsTrendChart(items) {
  const canvas = document.getElementById('ops-trend-chart');
  const empty = document.getElementById('ops-chart-empty');
  const card = canvas?.closest('.ops-chart-card');
  if (!canvas || !card) return;

  const rows = items
    .slice(0, 8)
    .map(item => ({ item, stats: opsStats(item) }))
    .filter(row => row.item?.name);

  if (!rows.length || typeof Chart === 'undefined') {
    card.classList.add('is-empty');
    if (empty) {
      empty.textContent = typeof Chart === 'undefined'
        ? '图表库未加载，请检查网络或稍后刷新。'
        : '暂无可视化数据，请先同步平台热度。';
    }
    return;
  }

  card.classList.remove('is-empty');
  const labels = rows.map(row => row.item.name.length > 5 ? `${row.item.name.slice(0, 5)}...` : row.item.name);
  const heatData = rows.map(row => Math.round(row.stats.heat));
  const engagementData = rows.map(row => Number((row.stats.engagementRate * 100).toFixed(1)));
  const maxHeat = Math.max(...heatData, 1);
  const ctx = canvas.getContext('2d');

  const chartData = {
    labels,
    datasets: [
      {
        type: 'bar',
        label: '综合热度',
        data: heatData,
        yAxisID: 'y',
        borderRadius: 8,
        borderSkipped: false,
        backgroundColor: heatData.map((value, index) => {
          const alpha = 0.28 + (value / maxHeat) * 0.42;
          return index === 0 ? `rgba(247, 111, 70, ${alpha + 0.18})` : `rgba(45, 212, 191, ${alpha})`;
        }),
        maxBarThickness: 22
      },
      {
        type: 'line',
        label: '互动率',
        data: engagementData,
        yAxisID: 'y1',
        borderColor: '#F76F46',
        backgroundColor: 'rgba(247,111,70,.14)',
        borderWidth: 2,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        pointBackgroundColor: '#FFFFFF',
        pointBorderColor: '#F76F46',
        pointBorderWidth: 2
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'start',
        labels: {
          boxWidth: 9,
          boxHeight: 9,
          usePointStyle: true,
          color: '#7D6257',
          font: { size: 10, weight: '700' }
        }
      },
      tooltip: {
        backgroundColor: '#2C1810',
        titleFont: { size: 11, weight: '800' },
        bodyFont: { size: 11 },
        padding: 10,
        callbacks: {
          label(context) {
            if (context.dataset.yAxisID === 'y1') return `互动率 ${context.parsed.y}%`;
            return `综合热度 ${opsMetric(context.parsed.y)}`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#9B7B70', font: { size: 9, weight: '700' }, maxRotation: 0, autoSkip: false }
      },
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(125,98,87,.12)' },
        ticks: { color: '#9B7B70', font: { size: 9 }, callback: value => opsMetric(value) }
      },
      y1: {
        position: 'right',
        beginAtZero: true,
        suggestedMax: Math.max(8, Math.ceil(Math.max(...engagementData, 0) * 1.35)),
        grid: { drawOnChartArea: false },
        ticks: { color: '#F76F46', font: { size: 9 }, callback: value => `${value}%` }
      }
    }
  };

  if (opsTrendChart) {
    opsTrendChart.data = chartData;
    opsTrendChart.options = chartOptions;
    opsTrendChart.update();
    return;
  }

  opsTrendChart = new Chart(ctx, {
    data: chartData,
    options: chartOptions
  });
}

function opsAssistantPayload(items, summary) {
  return {
    items: items.slice(0, 12).map(item => {
      const stats = opsStats(item);
      return {
        id: item.id,
        rank: item.rank,
        name: item.name,
        tags: item.tags || [],
        platformName: opsPlatformName(item),
        trendSource: item.trendSource,
        heatScore: stats.heat,
        stats: {
          view: stats.view,
          like: stats.like,
          collect: stats.collect,
          comment: stats.comment,
          share: stats.share,
          danmaku: stats.danmaku,
          coin: stats.coin,
          engagementRate: stats.engagementRate,
          collectRate: stats.collectRate
        }
      };
    }),
    summary: {
      styleTotal: summary.styleTotal,
      liveCount: summary.liveCount,
      fallbackCount: summary.fallbackCount,
      score: summary.score,
      top: summary.top ? {
        id: summary.top.id,
        name: summary.top.name,
        rank: summary.top.rank,
        platformName: opsPlatformName(summary.top)
      } : null,
      totals: summary.totals,
      averageView: summary.averageView,
      averageHeat: summary.averageHeat
    },
    trendBuckets: opsTrendBuckets(items).slice(0, 6).map(bucket => ({
      label: bucket.label,
      heat: bucket.heat,
      view: bucket.view,
      intent: bucket.intent,
      count: bucket.count,
      avgEngagement: bucket.avgEngagement,
      examples: bucket.examples.map(item => item.name)
    }))
  };
}

function renderOpsAssistantResult(result) {
  const box = document.getElementById('ops-assistant');
  if (!box || !result) return;
  const lines = Array.isArray(result.lines) ? result.lines.slice(0, 4) : [];
  if (!lines.length) return;
  const subtitle = result.source === 'modelscope'
    ? `ModelScope · ${result.model || 'Qwen'}`
    : '本地策略兜底 · 等待 ModelScope 返回';
  box.innerHTML = `
    <div class="ops-assistant-head">
      <div>
        <strong>${opsEscapeHtml(result.headline || 'ModelScope 智能运营助手')}</strong>
        <span>${opsEscapeHtml(subtitle)}</span>
      </div>
      <div class="ops-assistant-status">${opsEscapeHtml(result.status || (result.source === 'modelscope' ? 'AI' : 'LOCAL'))}</div>
    </div>
    <div class="ops-assistant-lines">
      ${lines.map(line => `
        <div class="ops-assistant-line">
          <b>${opsEscapeHtml(line.label)}</b>
          <span>${opsEscapeHtml(line.text)}</span>
        </div>`).join('')}
    </div>`;
}

async function refreshOpsAssistantModel(items, summary, force = false) {
  const payload = opsAssistantPayload(items, summary);
  const signature = JSON.stringify({
    ids: payload.items.map(item => `${item.id}:${item.rank}:${Math.round(item.heatScore || 0)}`),
    liveCount: payload.summary.liveCount,
    fallbackCount: payload.summary.fallbackCount
  });
  if (!force && signature === opsAssistantSignature) return;
  opsAssistantSignature = signature;
  const requestId = ++opsAssistantRequestId;

  try {
    const response = await fetch(`${OPS_API_BASE}/api/ops/assistant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (requestId !== opsAssistantRequestId) return;
    renderOpsAssistantResult(result);
  } catch (error) {
    const box = document.getElementById('ops-assistant');
    if (box) {
      const status = box.querySelector('.ops-assistant-head span');
      if (status) status.textContent = `ModelScope 暂未连接 · ${error.message}`;
    }
  }
}

function renderOpsTrendInsights(items, summary) {
  const box = document.getElementById('ops-trend-insights');
  if (!box) return;
  if (!items.length) {
    box.innerHTML = '<div class="ops-empty">暂无趋势数据。请先同步平台热度。</div>';
    return;
  }
  const buckets = opsTrendBuckets(items);
  const topBuckets = buckets.slice(0, 4);
  box.innerHTML = topBuckets.map(bucket => {
    const heatShare = summary.totals.heat ? bucket.heat / summary.totals.heat : 0;
    const examples = bucket.examples.map(item => item.name).join('、');
    return `
      <div class="ops-trend-card">
        <div class="ops-trend-top">
          <strong>${opsEscapeHtml(bucket.label)}</strong>
          <span>${opsTrendSignal(bucket, summary)}</span>
        </div>
        <div class="ops-trend-metrics">
          <div><b>${opsMetric(bucket.heat)}</b><small>聚合热度</small></div>
          <div><b>${opsPercent(bucket.avgEngagement)}</b><small>平均互动</small></div>
          <div><b>${Math.round(heatShare * 100)}%</b><small>热度占比</small></div>
        </div>
        <p>代表款：${opsEscapeHtml(examples || '暂无')}</p>
      </div>`;
  }).join('');
}

function renderOpsAssistant(items, summary) {
  const box = document.getElementById('ops-assistant');
  if (!box) return;
  if (!items.length) {
    box.innerHTML = '<div class="ops-empty">AI 助手等待平台数据同步。</div>';
    return;
  }
  const buckets = opsTrendBuckets(items);
  const topTrend = buckets[0];
  const topItem = summary.top || items[0];
  const secondItem = items[1] || topItem;
  const risk = items
    .map(item => ({ item, risk: opsRiskFor(item, summary) }))
    .sort((a, b) => b.risk.score - a.risk.score)[0];
  const liveText = summary.liveCount
    ? `已实时监控 ${summary.liveCount}/${summary.styleTotal} 款公开视频热度`
    : `当前使用本地参考热度，建议补齐公开视频或授权 API`;
  const trendText = topTrend
    ? `${topTrend.label}方向热度最高，聚合热度 ${opsMetric(topTrend.heat)}，平均互动率 ${opsPercent(topTrend.avgEngagement)}`
    : '暂无明显趋势方向';
  const strategyText = `今日主推「${topItem.name}」，搭配「${secondItem.name}」做同屏推荐，并把主推款接到 AI 试戴默认入口。`;
  const riskText = risk
    ? `优先处理「${risk.item.name}」：${risk.risk.action}`
    : '暂无明显风险款。';
  box.innerHTML = `
    <div class="ops-assistant-head">
      <div>
        <strong>OpenClaw-ready 运营助手</strong>
        <span>基于实时热度生成趋势判断与执行策略</span>
      </div>
      <div class="ops-assistant-status">AI</div>
    </div>
    <div class="ops-assistant-lines">
      <div class="ops-assistant-line"><b>实时监控</b><span>${opsEscapeHtml(liveText)}</span></div>
      <div class="ops-assistant-line"><b>趋势分析</b><span>${opsEscapeHtml(trendText)}</span></div>
      <div class="ops-assistant-line"><b>策略生成</b><span>${opsEscapeHtml(strategyText)}</span></div>
      <div class="ops-assistant-line"><b>效率提升</b><span>${opsEscapeHtml(riskText)}</span></div>
    </div>`;
  refreshOpsAssistantModel(items, summary);
}

function renderOpsEntrySummary() {
  const entry = document.getElementById('ops-entry-sub');
  if (!entry) return;
  const items = getOpsItems();
  const summary = opsSummary(items);
  if (!items.length) {
    entry.textContent = '等待款式库与平台热度同步';
    return;
  }
  const top = summary.top;
  entry.textContent = `${opsSourceText(summary)} · 监控 ${summary.liveCount || items.length}/${summary.styleTotal || items.length} 款 · 今日主推 ${top.name}`;
}

function renderOpsKpis(summary) {
  const box = document.getElementById('ops-kpis');
  if (!box) return;
  box.innerHTML = `
    <div class="ops-kpi">
      <div class="ops-kpi-label">实时监控款</div>
      <div class="ops-kpi-value">${summary.liveCount}/${summary.styleTotal || 0}</div>
      <div class="ops-kpi-note">${summary.fallbackCount ? `${summary.fallbackCount} 款使用本地参考` : '全部接入公开统计'}</div>
    </div>
    <div class="ops-kpi">
      <div class="ops-kpi-label">平台曝光</div>
      <div class="ops-kpi-value">${opsMetric(summary.totals.view)}</div>
      <div class="ops-kpi-note">按公开播放量汇总</div>
    </div>
    <div class="ops-kpi">
      <div class="ops-kpi-label">高意向互动</div>
      <div class="ops-kpi-value">${opsMetric(summary.totals.intent)}</div>
      <div class="ops-kpi-note">赞藏评转加权计算</div>
    </div>
    <div class="ops-kpi">
      <div class="ops-kpi-label">今日运营动作</div>
      <div class="ops-kpi-value">${Math.min(6, summary.styleTotal || 0)}</div>
      <div class="ops-kpi-note">主推、转化、补内容</div>
    </div>`;
}

function renderOpsStrategy(summary) {
  const box = document.getElementById('ops-strategy');
  if (!box) return;
  const item = summary.top;
  if (!item) {
    box.innerHTML = '<div class="ops-empty">暂无可分析款式。请先启动后端并加载款式库。</div>';
    return;
  }
  const stats = opsStats(item);
  const key = opsEscapeHtml(opsKey(item));
  const source = opsPlatformName(item);
  const image = item.image ? `<img src="${opsEscapeHtml(item.image)}" alt="${opsEscapeHtml(item.name)}">` : opsEscapeHtml(item.emoji || '💅');
  const platformAction = item.platformUrl
    ? `<a class="ops-action-btn ops-action-link" href="${opsEscapeHtml(item.platformUrl)}" target="_blank" rel="noopener">查看${source}视频</a>`
    : '';
  box.innerHTML = `
    <div class="ops-strategy-top">
      <button class="ops-strategy-thumb" data-ops-key="${key}" onclick="openOpsStyle(this.dataset.opsKey)">
        ${image}
      </button>
      <div class="ops-strategy-main">
        <h4>${opsEscapeHtml(item.name)}</h4>
        <p>#${item.rank} · ${opsEscapeHtml(opsStyleLine(item))} · ${source}</p>
      </div>
    </div>
    <div class="ops-strategy-grid">
      <div class="ops-mini-metric"><span>综合热度</span><strong>${opsMetric(stats.heat)}</strong></div>
      <div class="ops-mini-metric"><span>互动率</span><strong>${opsPercent(stats.engagementRate)}</strong></div>
      <div class="ops-mini-metric"><span>播放</span><strong>${opsMetric(stats.view)}</strong></div>
      <div class="ops-mini-metric"><span>收藏/投币</span><strong>${opsMetric(stats.collect + stats.coin)}</strong></div>
    </div>
    <div class="ops-strategy-copy">
      建议将「${opsEscapeHtml(item.name)}」作为今日主推：它当前在 ${source} 热度排序中领先，适合放在首页热门首位，并同步到 AI 试戴入口。详情页保留平台视频入口，让用户先看真实内容热度，再进入试戴决策。
    </div>
    <div class="ops-actions">
      <button class="ops-action-btn ops-action-primary" data-ops-key="${key}" onclick="openOpsStyle(this.dataset.opsKey)">查看款式</button>
      <button class="ops-action-btn ops-action-soft" data-ops-key="${key}" onclick="tryOpsStyle(this.dataset.opsKey)">设为试戴</button>
      ${platformAction}
    </div>`;
}

function renderOpsPriorityList(items, summary) {
  const box = document.getElementById('ops-priority-list');
  if (!box) return;
  const topItems = items.slice(0, 6);
  const maxHeat = Math.max(...topItems.map(item => opsStats(item).heat), 1);
  box.innerHTML = topItems.map((item, index) => {
    const stats = opsStats(item);
    const action = opsActionFor(item, index);
    const key = opsEscapeHtml(opsKey(item));
    const image = item.image ? `<img src="${opsEscapeHtml(item.image)}" alt="${opsEscapeHtml(item.name)}">` : opsEscapeHtml(item.emoji || '💅');
    const width = opsClamp(Math.round((stats.heat / maxHeat) * 100), 8, 100);
    return `
      <div class="ops-row">
        <button class="ops-row-thumb" data-ops-key="${key}" onclick="openOpsStyle(this.dataset.opsKey)">${image}</button>
        <div class="ops-row-main">
          <div class="ops-row-title">
            <strong>#${item.rank} ${opsEscapeHtml(item.name)}</strong>
            <span class="ops-pill ops-pill-${action.pill}">${action.label}</span>
          </div>
          <div class="ops-row-sub">${opsPlatformName(item)} · 播放 ${opsMetric(stats.view)} · 赞藏 ${opsMetric(stats.like + stats.collect)}</div>
          <div class="ops-progress"><span style="width:${width}%"></span></div>
          <div class="ops-row-action">${action.desc}</div>
        </div>
        <button class="ops-row-try" data-ops-key="${key}" onclick="tryOpsStyle(this.dataset.opsKey)">试戴</button>
      </div>`;
  }).join('');
}

function renderOpsRiskList(items, summary) {
  const box = document.getElementById('ops-risk-list');
  if (!box) return;
  const risks = items
    .map(item => ({ item, risk: opsRiskFor(item, summary) }))
    .sort((a, b) => b.risk.score - a.risk.score)
    .slice(0, 4);
  box.innerHTML = risks.map(({ item, risk }) => `
    <div class="ops-row">
      <div class="ops-risk-mark">!</div>
      <div class="ops-row-main">
        <div class="ops-row-title">
          <strong>${opsEscapeHtml(item.name)}</strong>
          <span class="ops-pill ops-pill-watch">${risk.issue}</span>
        </div>
        <div class="ops-row-sub">${opsPlatformName(item)} · #${item.rank} · ${opsMetric(opsStats(item).heat)} 热度</div>
        <div class="ops-row-action">${risk.action}</div>
      </div>
    </div>`).join('');
}

function renderOpsPlan(items, summary) {
  const box = document.getElementById('ops-plan');
  if (!box) return;
  const first = items[0];
  const second = items[1] || first;
  const risk = items.map(item => ({ item, risk: opsRiskFor(item, summary) })).sort((a, b) => b.risk.score - a.risk.score)[0]?.item || first;
  if (!first) {
    box.innerHTML = '<div class="ops-empty">暂无执行方案。</div>';
    return;
  }
  const steps = [
    ['09:30', `首页主推「${first.name}」`, `将该款放到今日热门首位，详情页展示平台热度和相关视频入口。`],
    ['11:00', `试戴承接「${first.name}」`, `把 AI 试戴默认款切到主推款，缩短用户从浏览到上手效果验证的路径。`],
    ['15:30', `组合推荐「${second.name}」`, `用同风格或同色系款做二选一推荐，提升停留和对比决策效率。`],
    ['20:30', `复盘「${risk.name}」`, `检查低热或数据缺口款，补封面、补视频链接，并记录下一轮排序变化。`]
  ];
  box.innerHTML = steps.map(([time, title, text]) => `
    <div class="ops-plan-step">
      <div class="ops-plan-time">${time}</div>
      <div class="ops-plan-main">
        <strong>${opsEscapeHtml(title)}</strong>
        <span>${opsEscapeHtml(text)}</span>
      </div>
    </div>`).join('');
}

function renderOpsDashboard() {
  const score = document.getElementById('ops-score-num');
  if (!score) {
    renderOpsEntrySummary();
    return;
  }
  const items = getOpsItems();
  opsLastItems = items;
  const summary = opsSummary(items);
  const heroCopy = document.getElementById('ops-hero-copy');
  const updated = document.getElementById('ops-updated');

  score.textContent = summary.score || '--';
  if (heroCopy) {
    heroCopy.textContent = summary.top
      ? `今日优先主推「${summary.top.name}」，并对低热款安排内容补强。`
      : '等待款式库和平台数据同步后生成运营策略。';
  }
  if (updated) {
    const message = summary.state?.status === 'error' ? ` · ${summary.state.message || '实时接口异常'}` : '';
    updated.textContent = `${opsSourceText(summary)} · 更新于 ${opsFormatTime(summary.state?.updatedAt)}${message}`;
  }

  renderOpsEntrySummary();
  renderOpsKpis(summary);
  renderOpsTrendChart(items);
  renderOpsTrendInsights(items, summary);
  renderOpsStrategy(summary);
  renderOpsPriorityList(items, summary);
  renderOpsRiskList(items, summary);
  renderOpsPlan(items, summary);
  renderOpsAssistant(items, summary);
}

async function refreshOpsDashboard(force = false) {
  if (force && typeof refreshXhsTrending === 'function') {
    const updated = document.getElementById('ops-updated');
    if (updated) updated.textContent = '正在刷新平台热度...';
    await refreshXhsTrending();
    renderOpsDashboard();
    refreshOpsAssistantModel(opsLastItems, opsSummary(opsLastItems), true);
    if (typeof showToast === 'function') showToast('运营数据已刷新');
    return;
  }
  renderOpsDashboard();
  if (force) refreshOpsAssistantModel(opsLastItems, opsSummary(opsLastItems), true);
}

function openOpsStyle(key) {
  const item = opsLastItems.find(row => opsKey(row) === key);
  if (!item || typeof goDetail !== 'function') return;
  goDetail(item.emoji, item.name, item.sub || opsStyleLine(item), item.price, item.bg, item.image, item.id);
}

function tryOpsStyle(key) {
  const item = opsLastItems.find(row => opsKey(row) === key);
  if (!item) return;
  if (typeof setTryonStyle === 'function') {
    setTryonStyle(item.emoji, item.name, item.price, item.bg, item.image);
  }
  if (typeof go === 'function') go('s-tryon');
}
