/* ══════════════════════════════════
   TRY-ON  —  连接后端 API
══════════════════════════════════ */

// 后端地址（与 main.py 保持一致）
const API_BASE = window.API_BASE;

// 缓存上传的手图与当前款式，供颜色切换复用
let lastTryonFile = null;
let currentTryonColor = null;
let isGeneratedDesign = false;  // 标记是否是 AI 生成的设计

// 灵感图生成的design_id
let inspirationDesignId = null;

// ── 灵感图试戴 ─────────────────────────
async function handleInspirationUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const loadingEl = document.getElementById('inspiration-loading');
  const resultEl = document.getElementById('inspiration-result');
  const statusEl = document.getElementById('inspiration-status');
  const progressBar = document.getElementById('inspiration-progress-bar');

  loadingEl.style.display = 'block';
  resultEl.style.display = 'none';

  // 进度条动画
  let progress = 0;
  const progressSteps = [
    { pct: 15, msg: '分析灵感图设计...', delay: 500 },
    { pct: 35, msg: 'AI提取美甲特征...', delay: 2000 },
    { pct: 60, msg: 'AI生成模具图...', delay: 5000 },
    { pct: 85, msg: '切割5个单指模具...', delay: 3000 },
  ];

  let stepIdx = 0;
  const progressTimer = setInterval(() => {
    if (stepIdx < progressSteps.length) {
      const step = progressSteps[stepIdx];
      progress = step.pct;
      progressBar.style.width = `${progress}%`;
      statusEl.textContent = step.msg;
      stepIdx++;
    }
  }, 4000);

  try {
    const formData = new FormData();
    formData.append('image', file);

    const resp = await fetch(`${API_BASE}/api/generate-mold-from-inspiration`, {
      method: 'POST',
      body: formData
    });

    clearInterval(progressTimer);

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (data.success) {
      progressBar.style.width = '100%';
      statusEl.textContent = '模具生成成功！';

      setTimeout(() => {
        loadingEl.style.display = 'none';
        resultEl.style.display = 'block';

        // 显示预览图
        const previewImg = document.getElementById('inspiration-template-preview');
        previewImg.src = `data:image/jpeg;base64,${data.template_base64}`;

        // 显示设计描述
        document.getElementById('inspiration-design-desc').textContent = `🎨 ${data.design_description}`;

        // 保存design_id供试戴使用
        inspirationDesignId = data.design_id;
      }, 500);
    } else {
      loadingEl.style.display = 'none';
      showToast(data.message || '生成失败，请重试');
    }
  } catch (e) {
    clearInterval(progressTimer);
    loadingEl.style.display = 'none';
    console.error('[InspirationTryOn] 错误:', e);
    showToast('生成失败: ' + e.message);
  }

  // 清空文件选择
  event.target.value = '';
}

function startInspirationTryon() {
  if (!inspirationDesignId) {
    showToast('请先上传灵感图');
    return;
  }

  // 设置款式为灵感图生成的款式
  isGeneratedDesign = true;
  tryonStyleInfo = {
    name: '灵感款式',
    emoji: '✨',
    image: '',
    designId: inspirationDesignId
  };

  // 更新UI显示
  const nameEl = document.getElementById('tryon-style-name');
  if (nameEl) nameEl.textContent = '灵感款式 ✨';

  // 跳转到试戴页面
  if (typeof go === 'function') go('s-tryon');
  showToast('款式已设置，请上传手部照片开始试戴！');
}

// 甲形参数
let nailShape = "oval";     // oval / almond / square
let nailLength = 1.0;       // 0.5-1.5
let nailWidth = 1.0;        // 0.5-1.5

// 防抖和请求取消控制
let _applyTryonDebounceTimer = null;
let _applyTryonAbortController = null;

// 指甲旋转角度（用户调整）
let nailAngles = {
  "0": 0,  // 拇指
  "1": 0,  // 食指
  "2": 0,  // 中指
  "3": 0,  // 无名指
  "4": 0   // 小指
};

// 手指旋转控制的展开/折叠状态
let fingersExpanded = {
  "0": false,
  "1": false,
  "2": false,
  "3": false,
  "4": false
};

// 检测预览结果缓存
let lastDetectionResult = null;

// 颜色切换预设色板（含可换色的常用美甲色）
const TRYON_COLOR_PALETTE = [
  { hex: '',        name: '原款' },
  { hex: '#C0392B', name: '正红' },
  { hex: '#E8A0BF', name: '樱花粉' },
  { hex: '#8E6FB0', name: '雾紫' },
  { hex: '#5B8C5A', name: '牛油果绿' },
  { hex: '#6B4F3A', name: '焦糖' },
  { hex: '#2C2C2C', name: '墨黑' },
  { hex: '#E8D5B0', name: '裸杏' },
  { hex: '#4A6FA5', name: '海岛蓝' },
];

function _refreshStyleCard() {
  const noStyle = document.getElementById('tryon-no-style');
  const hasStyle = document.getElementById('tryon-has-style');
  const hasSelection = tryonStyleInfo && tryonStyleInfo.name;
  if (noStyle) noStyle.style.display = hasSelection ? 'none' : 'flex';
  if (hasStyle) hasStyle.style.display = hasSelection ? 'flex' : 'none';
}

function clearTryonStyle() {
  tryonStyleInfo = { emoji: '', name: '', price: '', bg: '', image: '', designId: '' };
  isGeneratedDesign = false;
  _refreshStyleCard();
}

function setTryonStyle(emoji, name, price, bg, image, designId = null) {
  tryonStyleInfo = { emoji, name, price, bg, image: image || '', designId: designId || '' };
  isGeneratedDesign = !!designId;
  console.log('[TryOn] 选中款式:', name, '| image:', image || '(空)', '| designId:', designId || '(空)');
  const box = document.getElementById('tryon-thumb-box');
  if (box) {
    box.style.background = bg;
    if (image) {
      box.innerHTML = `<img src="${image}" alt="${name}" style="width:100%;height:100%;object-fit:cover;border-radius:var(--rMd)">`;
    } else {
      box.textContent = emoji;
    }
  }
  const lbl = document.getElementById('tryon-style-name');
  if (lbl) lbl.textContent = name;

  // 切换到已选款式状态
  _refreshStyleCard();

  // 清空之前的试戴结果
  const resultEl = document.getElementById('tryon-result');
  if (resultEl) {
    const previewEmoji = document.getElementById('tryon-result-emoji');
    if (previewEmoji) previewEmoji.textContent = emoji;
  }

  // 重置分析数据
  analysisData = null;

  // 清空进度条
  for (let i = 1; i <= 4; i++) {
    const step = document.getElementById(`ps${i}`);
    if (step) step.className = 'pstep';
  }
}

// 初始化：检查是否有 AI 生成的设计待试戴
function initGeneratedDesignIfExists() {
  const stored = sessionStorage.getItem('selectedGeneratedDesign');
  if (stored) {
    try {
      const design = JSON.parse(stored);
      console.log('[TryOn] 加载 AI 生成的设计:', design);
      // 优先用 preview（AI 生成的完整设计图），thumbnail（扇形预览）兜底
      const relativeImg = design.preview || design.thumbnail || '';
      const imgUrl = relativeImg ? `${API_BASE}${relativeImg}` : '';
      const shortName = (design.prompt || 'AI 生成款式').slice(0, 20);
      setTryonStyle('✨', shortName, 0, '#FFF9E6', imgUrl, design.id);
      sessionStorage.removeItem('selectedGeneratedDesign');  // 清除后不再自动加载
    } catch (e) {
      console.error('[TryOn] 解析生成设计失败:', e);
    }
  }
}

// ── 步骤动画 ──────────────────────────
function setStep(id, text, done) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = 'pstep' + (done ? ' done' : '');
}

// ── 显示结果 ──────────────────────────
function showTryonResult(imageBase64, analysisData, nApplied) {
  const resultEl = document.getElementById('tryon-result');
  const emojiEl  = document.getElementById('tryon-result-emoji');

  console.log('[TryOn] showTryonResult 被调用，图片前50字符:', imageBase64?.substring(0, 50));

  // 显示真实图像 or emoji
  if (imageBase64) {
    console.log('[TryOn] 更新图片元素...');
    const imgSrc = `data:image/jpeg;base64,${imageBase64}`;
    emojiEl.innerHTML = `<img src="${imgSrc}"
      style="width:100%;max-height:220px;object-fit:contain;border-radius:12px;" alt="试戴效果">`;
  } else {
    emojiEl.textContent = tryonStyleInfo.emoji;
  }

  const labelSuffix = currentTryonColor ? '（换色）' : '';
  document.getElementById('tryon-result-label').textContent =
    `效果预览 · ${tryonStyleInfo.name}${labelSuffix}`;

  // 填入 AI 分析数据
  if (analysisData) {
    // 肤色匹配度
    const confidence = analysisData.confidence
      ? Math.round(analysisData.confidence * 100) + '%'
      : '—';
    document.getElementById('tryon-match-score').textContent = confidence;

    // 肤色
    const skinTone = analysisData.skin_tone || '—';
    const skinToneEl = document.getElementById('tryon-skin-tone');
    if (skinToneEl) skinToneEl.textContent = skinTone;

    // 手型评级
    const handRating = analysisData.hand_rating || '—';
    const handRatingEl = document.getElementById('tryon-hand-rating');
    if (handRatingEl) handRatingEl.textContent = handRating;

    // AI 分析文本
    const aiText = analysisData.description
      || analysisData.why_match
      || '分析生成中...';
    document.getElementById('tryon-ai-text').textContent = aiText;

    // 色系推荐
    if (analysisData.best_color_systems) {
      const primary = analysisData.best_color_systems.primary || '—';
      const recPrimaryEl = document.getElementById('rec-primary');
      if (recPrimaryEl) recPrimaryEl.textContent = primary;
    }

    // 风格推荐
    if (analysisData.style_recommendations && Array.isArray(analysisData.style_recommendations)) {
      const styles = analysisData.style_recommendations.join('、') || '—';
      const recStylesEl = document.getElementById('rec-styles');
      if (recStylesEl) recStylesEl.textContent = styles;
    }

    console.log('[TryOn] AI 分析数据更新: 匹配度=', confidence, '肤色=', skinTone, '手型=', handRating);
  }

  // 少于等于3个指甲时显示警告
  const existingWarning = document.getElementById('tryon-nail-count-warning');
  if (existingWarning) existingWarning.remove();
  if (nApplied != null && nApplied <= 3) {
    const warning = document.createElement('div');
    warning.id = 'tryon-nail-count-warning';
    warning.style.cssText = 'margin-top:10px;padding:10px 14px;background:#fff8e1;border-left:3px solid #f5a623;border-radius:6px;font-size:13px;color:#7a5c00;line-height:1.5';
    warning.textContent = `仅检测到 ${nApplied} 个指甲，试戴效果欠佳，建议重新上传清晰的手部正面照片。`;
    emojiEl.parentElement.appendChild(warning);
  }

  renderNailShapePanel();
  renderNailRotationPanel();
  resultEl.classList.add('show');
  if (typeof addTryonHistory === 'function') {
    addTryonHistory({
      source: 'AI试戴',
      resultImage: imageBase64 ? `data:image/jpeg;base64,${imageBase64}` : '',
      matchScore: document.getElementById('tryon-match-score')?.textContent || '—'
    });
  }
}

// ── 甲形控制面板 ──────────────────────
function renderNailShapePanel() {
  // 创建或获取调整面板容器
  let container = document.getElementById('tryon-adjustment-container');
  if (!container) {
    const card = document.querySelector('#tryon-result .result-preview');
    if (!card) return;
    container = document.createElement('div');
    container.id = 'tryon-adjustment-container';
    container.style.cssText = 'margin-top:16px;display:flex;gap:12px';
    card.appendChild(container);
  }

  // 获取或创建指甲调整面板
  let box = document.getElementById('tryon-nail-shape-panel');
  if (!box) {
    box = document.createElement('div');
    box.id = 'tryon-nail-shape-panel';
    box.style.cssText = 'flex:1;padding:12px;background:var(--bg);border-radius:var(--rMd);border:1px solid var(--border)';
    container.appendChild(box);
  } else {
    // 清除旧内容，避免重复
    box.innerHTML = '';
  }

  box.innerHTML = `
    <div style="font-size:11px;color:var(--text-soft);margin-bottom:8px">⚙️ 指甲调整</div>

    <div style="margin-bottom:10px">
      <div style="font-size:11px;color:var(--text-dark);margin-bottom:6px">形状</div>
      <div style="display:flex;gap:6px">
        <button style="flex:1;padding:6px;border:${nailShape==='oval'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:10px;cursor:pointer;font-weight:${nailShape==='oval'?'700':'400'};white-space:nowrap" onclick="updateNailShape('oval')">椭圆</button>
        <button style="flex:1;padding:6px;border:${nailShape==='almond'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:10px;cursor:pointer;font-weight:${nailShape==='almond'?'700':'400'};white-space:nowrap" onclick="updateNailShape('almond')">尖形</button>
        <button style="flex:1;padding:6px;border:${nailShape==='square'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:10px;cursor:pointer;font-weight:${nailShape==='square'?'700':'400'};white-space:nowrap" onclick="updateNailShape('square')">方形</button>
      </div>
    </div>

    <div style="margin-bottom:10px">
      <div style="font-size:11px;color:var(--text-dark);margin-bottom:6px;display:flex;align-items:center;gap:6px;white-space:nowrap">
        长度: <span style="color:var(--orange);min-width:30px">${(nailLength*100).toFixed(0)}%</span>
        <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="decreaseNailLength()">−</button>
        <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="increaseNailLength()">+</button>
      </div>
      <input type="range" min="50" max="150" value="${nailLength*100}" step="5"
        style="width:100%;height:4px;cursor:pointer"
        oninput="updateNailLength(this.value)">
    </div>

    <div>
      <div style="font-size:11px;color:var(--text-dark);margin-bottom:6px;display:flex;align-items:center;gap:6px;white-space:nowrap">
        宽度: <span style="color:var(--orange);min-width:30px">${(nailWidth*100).toFixed(0)}%</span>
        <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="decreaseNailWidth()">−</button>
        <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="increaseNailWidth()">+</button>
      </div>
      <input type="range" min="50" max="150" value="${nailWidth*100}" step="5"
        style="width:100%;height:4px;cursor:pointer"
        oninput="updateNailWidth(this.value)">
    </div>
  `;
}

function updateNailShape(shape) {
  nailShape = shape;
  // 立即重新渲染面板显示新的形状
  renderNailShapePanel();
  // 异步更新试戴结果，不用等待
  applyTryonColor(currentTryonColor);
}

function updateNailLength(val) {
  nailLength = parseFloat(val) / 100.0;
  // 立即重新渲染面板显示新的长度
  renderNailShapePanel();
  // 异步更新试戴结果，不用等待
  applyTryonColor(currentTryonColor);
}

function updateNailWidth(val) {
  nailWidth = parseFloat(val) / 100.0;
  // 立即重新渲染面板显示新的宽度
  renderNailShapePanel();
  // 异步更新试戴结果，不用等待
  applyTryonColor(currentTryonColor);
}

function increaseNailLength() {
  const newVal = Math.min(150, Math.round((nailLength * 100) + 5));
  updateNailLength(newVal);
}

function decreaseNailLength() {
  const newVal = Math.max(50, Math.round((nailLength * 100) - 5));
  updateNailLength(newVal);
}

function increaseNailWidth() {
  const newVal = Math.min(150, Math.round((nailWidth * 100) + 5));
  updateNailWidth(newVal);
}

function decreaseNailWidth() {
  const newVal = Math.max(50, Math.round((nailWidth * 100) - 5));
  updateNailWidth(newVal);
}

// ── 指甲旋转调整面板 ────────────────────
function renderNailRotationPanel() {
  // 获取或创建调整面板容器
  let container = document.getElementById('tryon-adjustment-container');
  if (!container) {
    const card = document.querySelector('#tryon-result .result-preview');
    if (!card) return;
    container = document.createElement('div');
    container.id = 'tryon-adjustment-container';
    container.style.cssText = 'margin-top:16px;display:flex;gap:12px';
    card.appendChild(container);
  }

  // 获取或创建旋转调整面板
  let box = document.getElementById('tryon-nail-rotation-panel');
  if (!box) {
    box = document.createElement('div');
    box.id = 'tryon-nail-rotation-panel';
    box.style.cssText = 'flex:1;padding:12px;background:var(--bg);border-radius:var(--rMd);border:1px solid var(--border)';
    container.appendChild(box);
  } else {
    box.innerHTML = '';
  }

  const fingerNames = ['拇指', '食指', '中指', '无名指', '小指'];
  let html = `<div style="font-size:11px;color:var(--text-soft);margin-bottom:8px">🔄 方向调整</div>`;

  // 快捷旋转按钮
  html += `<div style="display:flex;gap:6px;margin-bottom:6px">
    <button style="flex:1;padding:6px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark);white-space:nowrap" onclick="quickRotateAllNails(90)">快速90°</button>
    <button style="flex:1;padding:6px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark);white-space:nowrap" onclick="quickRotateAllNails(180)">快速180°</button>
  </div>`;

  // 按检测到的指甲实际位置（从左到右）排序
  let nailList = [];
  if (lastDetectionResult && lastDetectionResult.nails_bounds && lastDetectionResult.nails_bounds.length > 0) {
    nailList = [...lastDetectionResult.nails_bounds].sort((a, b) => a.cx - b.cx);
  } else {
    // 没有检测结果时，显示默认5个
    nailList = [0, 1, 2, 3, 4].map(i => ({ id: i, cx: i * 0.2 }));
  }

  html += `<div style="display:grid;grid-template-columns:1fr;gap:6px">`;

  for (const nail of nailList) {
    const i = nail.id;
    const fingerKey = String(i);
    const fingerName = fingerNames[i] || `指甲${i}`;
    // 位置提示：左/中/右
    const posHint = nail.cx < 0.33 ? '左' : nail.cx < 0.66 ? '中' : '右';
    const currentAngle = nailAngles[fingerKey] ?? 0;
    const isExpanded = fingersExpanded[fingerKey];

    html += `
      <div style="padding:2px;background:var(--white);border-radius:4px;border:1px solid var(--border)">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;white-space:nowrap">
          <div style="font-size:10px;color:var(--text-dark);font-weight:500;white-space:nowrap">${fingerName} <span style="color:var(--text-soft);font-weight:400">(${posHint})</span></div>
          <div style="display:flex;align-items:center;gap:6px">
            <div style="font-size:10px;color:var(--text-soft);min-width:28px;text-align:center" id="angle-display-${i}">${currentAngle}°</div>
            <button style="padding:2px 6px;border:none;background:transparent;cursor:pointer;font-size:11px;color:var(--text-soft)" onclick="toggleFingerExpand('${fingerKey}')">${isExpanded ? '▼' : '▶'}</button>
          </div>
        </div>
        ${isExpanded ? `
          <input type="range" min="0" max="360" value="${currentAngle}" step="1"
            style="width:100%;height:4px;cursor:pointer;margin-bottom:4px"
            onchange="updateNailRotation('${fingerKey}', this.value)">
          <div style="font-size:10px;color:var(--text-soft);margin-bottom:4px;display:flex;align-items:center;justify-content:center;gap:4px">
            <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', -10)">−</button>
            <span style="min-width:30px;text-align:center">${currentAngle}°</span>
            <button style="padding:4px 8px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', 10)">+</button>
          </div>
          <div style="display:flex;gap:4px">
            <button style="flex:1;padding:4px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', -45)">−45</button>
            <button style="flex:1;padding:4px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', 45)">+45</button>
            <button style="flex:1;padding:4px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', 90)">90</button>
            <button style="flex:1;padding:4px;border:1px solid var(--border);background:var(--white);border-radius:4px;font-size:10px;cursor:pointer;color:var(--text-dark)" onclick="rotateNail('${fingerKey}', 180)">180</button>
          </div>
        ` : ''}
      </div>
    `;
  }

  html += '</div>';
  box.innerHTML = html;
}

function updateNailRotation(fingerKey, angleValue) {
  const angle = parseFloat(angleValue);
  if (isNaN(angle)) return;
  nailAngles[fingerKey] = angle;

  // 立即重新渲染旋转面板显示新的角度
  renderNailRotationPanel();

  // 异步更新试戴结果，不用等待
  applyTryonColor(currentTryonColor);
}

function rotateNail(fingerKey, angleDelta) {
  const currentAngle = nailAngles[fingerKey] ?? 0;
  let newAngle = (currentAngle + angleDelta) % 360;
  if (newAngle < 0) newAngle += 360;
  updateNailRotation(fingerKey, newAngle);
}

function quickRotateAllNails(angle) {
  for (let i = 0; i < 5; i++) {
    nailAngles[String(i)] = angle;
    const displayEl = document.getElementById(`angle-display-${i}`);
    if (displayEl) {
      const spanEl = displayEl.querySelector('span');
      if (spanEl) spanEl.textContent = `${angle}°`;
    }
  }
  applyTryonColor(currentTryonColor);
}

function toggleFingerExpand(fingerKey) {
  fingersExpanded[fingerKey] = !fingersExpanded[fingerKey];
  renderNailRotationPanel();
}

// 改变甲形 → 用缓存手图重新试戴（传递甲形参数）
async function applyTryonColor(hex) {
  if (!lastTryonFile) { showToast && showToast('请先上传照片试戴'); return; }
  currentTryonColor = hex || null;

  // 防抖：300ms内连续调用只执行最后一次
  if (_applyTryonDebounceTimer) clearTimeout(_applyTryonDebounceTimer);
  _applyTryonDebounceTimer = setTimeout(async () => {
    // 取消上一个未完成的请求
    if (_applyTryonAbortController) {
      _applyTryonAbortController.abort();
    }
    _applyTryonAbortController = new AbortController();

    const label = document.getElementById('tryon-result-label');
    if (label) label.textContent = `效果预览 · ${tryonStyleInfo.name}（处理中…）`;

    try {
      const designImageOrId = isGeneratedDesign ? tryonStyleInfo.designId : tryonStyleInfo.image;
      const data = await requestTryOn(lastTryonFile, designImageOrId, currentTryonColor, true, _applyTryonAbortController.signal);
      console.log('[TryOn] 响应:', { success: data.success, hasImage: !!data.image_base64 });
      if (data.success) {
        showTryonResult(data.image_base64, data.analysis || analysisData, data.n_applied);
        renderNailShapePanel();
        renderNailRotationPanel();
      } else {
        console.error('[TryOn] 试戴失败:', data.message);
        showToast && showToast(data.message || '更新失败');
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        console.log('[TryOn] 请求已取消（新请求覆盖）');
        return;
      }
      console.error('[TryOn] 异常:', e);
      showToast && showToast('更新失败，请重试');
    }
  }, 300);
}

// ── 统一的试戴请求 ────────────────────
async function requestTryOn(file, designImageOrId, color, skipAnalysis = false, signal = null) {
  const formData = new FormData();
  formData.append('image', file);

  let url = `${API_BASE}/api/try-on`;
  if (isGeneratedDesign) {
    url += `?design_id=${encodeURIComponent(designImageOrId)}`;
  } else {
    url += `?design_image=${encodeURIComponent(designImageOrId)}`;
  }
  if (color) url += `&color=${encodeURIComponent(color)}`;
  url += `&shape=${encodeURIComponent(nailShape)}`;
  url += `&length=${nailLength}`;
  url += `&width=${nailWidth}`;
  const validAngles = Object.fromEntries(
    Object.entries(nailAngles).filter(([, v]) => v !== null && v !== undefined && !isNaN(v))
  );
  url += `&nail_angles=${encodeURIComponent(JSON.stringify(validAngles))}`;
  if (skipAnalysis) url += `&skip_analysis=1`;

  // 注：暂不发送nails_bounds避免URL过长，后端会自动检测
  // if (lastDetectionResult && lastDetectionResult.nails_bounds) {
  //   url += `&nails_bounds=${encodeURIComponent(JSON.stringify(lastDetectionResult.nails_bounds))}`;
  // }

  console.log('[TryOn] 请求参数:', {
    color: color,
    shape: nailShape,
    length: nailLength,
    width: nailWidth,
    hasNailAngles: Object.keys(nailAngles).length > 0
  });

  const fetchOptions = { method: 'POST', body: formData };
  if (signal) fetchOptions.signal = signal;

  const response = await fetch(url, fetchOptions);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

// ── 主流程 ────────────────────────────
async function startTryon() {
  const fileInput = document.getElementById('tryon-file');
  const file = fileInput.files[0];
  if (!file) return;
  lastTryonFile = file;          // 缓存供换色复用
  currentTryonColor = null;      // 新试戴重置为原款

  // 隐藏上传区域，显示检测预览
  document.getElementById('tryon-upload').style.display = 'none';
  document.getElementById('tryon-tips').style.display = 'none';
  const previewEl = document.getElementById('tryon-detection-preview');
  previewEl.style.display = 'block';

  // 重置进度条
  const progressBar = document.getElementById('tryon-progress-bar');
  const progressPercent = document.getElementById('tryon-progress-percent');
  if (progressBar) progressBar.style.width = '0%';
  if (progressPercent) progressPercent.textContent = '0%';

  try {
    console.log('[TryOn] 调用检测预览 API...');
    const previewData = await detectNailsPreview(file);

    if (previewData.success) {
      console.log('[TryOn] 检测成功，显示预览');
      lastDetectionResult = previewData;
      displayDetectionPreview(previewData);
    } else {
      showToast && showToast(previewData.message || '检测失败');
      previewEl.style.display = 'none';
      document.getElementById('tryon-upload').style.display = 'flex';
      document.getElementById('tryon-file').value = '';
    }
  } catch (err) {
    console.error('[TryOn] 检测预览失败:', err);
    showToast && showToast('检测失败，请重试');
    previewEl.style.display = 'none';
    document.getElementById('tryon-upload').style.display = 'flex';
    document.getElementById('tryon-file').value = '';
  }
}

// ── 检测预览 API 调用 ──────────────
async function detectNailsPreview(file) {
  // ===== 清空所有之前的检测和试戴数据 =====
  lastDetectionResult = null;
  // 注：不清空 lastTryonFile，它在 startTryon 中设置，这里清空会导致后续试戴失败
  nailShape = 'oval';
  nailLength = 1.0;
  nailWidth = 1.0;
  nailAngles = {};
  fingersExpanded = {};
  currentTryonColor = null;
  analysisData = null;

  // 清空UI - 进度条和消息
  const progressBar = document.getElementById('tryon-progress-bar');
  if (progressBar) progressBar.style.width = '0%';
  const progressPercent = document.getElementById('tryon-progress-percent');
  if (progressPercent) progressPercent.textContent = '0%';

  // 清空预览图片内容（但保留元素可见，待检测完成后填充）
  const previewImg = document.getElementById('tryon-preview-image');
  if (previewImg) {
    previewImg.innerHTML = '';
  }

  // 隐藏试戴结果卡片和调整面板
  const resultEl = document.getElementById('tryon-result');
  if (resultEl) resultEl.classList.remove('show');
  const adjustContainer = document.getElementById('tryon-adjustment-container');
  if (adjustContainer) adjustContainer.remove();

  // 显示预览卡片
  const previewCard = document.getElementById('tryon-detection-preview');
  const progressMsg = document.getElementById('tryon-progress-message');
  const spinner = document.getElementById('spinner');

  if (previewCard) previewCard.style.display = 'block';
  if (spinner) spinner.style.display = 'inline-block';

  // 上传文件到后端流接口
  const formData = new FormData();
  formData.append('image', file);

  const response = await fetch(`${API_BASE}/api/detect-nails-preview`, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const data = await response.json();

  // 显示进度消息和进度条
  if (data.progress && Array.isArray(data.progress)) {
    const totalSteps = data.progress.length;
    for (let idx = 0; idx < data.progress.length; idx++) {
      const msg = data.progress[idx];
      if (progressMsg) progressMsg.textContent = msg;

      // 更新进度条
      const progress = Math.round(((idx + 1) / totalSteps) * 100);
      const progressBar = document.getElementById('tryon-progress-bar');
      const progressPercent = document.getElementById('tryon-progress-percent');
      if (progressBar) progressBar.style.width = progress + '%';
      if (progressPercent) progressPercent.textContent = progress + '%';

      await new Promise(resolve => setTimeout(resolve, 300));
    }
  }

  // 显示检测结果
  if (data.success) {
    if (data.image_data && previewImg) {
      // 设置图片src
      previewImg.src = data.image_data;

      // 使用onload事件显示按钮
      const showButtons = () => {
        console.log('[DetectNails] 预览图加载完成，显示按钮');
        const buttonsEl = document.getElementById('tryon-detection-buttons');
        if (buttonsEl) {
          buttonsEl.style.display = 'flex';
        }
        if (spinner) spinner.style.display = 'none';
      };

      // 如果图片已缓存，onload可能不会触发，所以用setTimeout备用
      previewImg.onload = showButtons;
      previewImg.onerror = () => {
        console.warn('[DetectNails] 预览图加载失败');
        showButtons();
      };

      // 如果1秒后onload还没触发，强制显示按钮
      setTimeout(() => {
        const buttonsEl = document.getElementById('tryon-detection-buttons');
        if (buttonsEl && buttonsEl.style.display === 'none') {
          showButtons();
        }
      }, 1000);
    } else {
      if (spinner) spinner.style.display = 'none';
      const buttonsEl = document.getElementById('tryon-detection-buttons');
      if (buttonsEl) buttonsEl.style.display = 'flex';
    }
    return data;
  } else {
    if (spinner) spinner.style.display = 'none';
    throw new Error(data.message || '检测失败');
  }
}

// ── 显示检测预览 ──────────────
function displayDetectionPreview(detectionData) {
  const previewImg = document.getElementById('tryon-preview-image');
  const canvas = document.getElementById('tryon-detection-canvas');
  const msgEl = document.getElementById('tryon-detection-message');

  // 显示后端返回的完整图片（已包含彩色掩码和标签）
  previewImg.src = detectionData.image_data;
  previewImg.onload = () => {
    // 清除 Canvas（后端已经绘制了所有内容）
    canvas.width = previewImg.width;
    canvas.height = previewImg.height;
    msgEl.textContent = detectionData.message;
  };
}

// ── 用 Canvas 绘制指甲边界框 ──
function drawNailBounds(canvas, image, nails_bounds) {
  canvas.width = image.width;
  canvas.height = image.height;
  const ctx = canvas.getContext('2d');

  // 颜色列表（用于区分不同的指甲）
  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'];

  nails_bounds.forEach((nail, idx) => {
    const color = colors[idx % colors.length];

    // 将相对坐标转换为像素坐标
    const cx = nail.cx * image.width;
    const cy = nail.cy * image.height;
    const w = nail.width * image.width;
    const h = nail.height * image.height;
    const angle = (nail.angle || 0) * Math.PI / 180;

    // 保存当前画布状态
    ctx.save();

    // 移动到中心点，旋转
    ctx.translate(cx, cy);
    ctx.rotate(angle);

    // 绘制旋转矩形（边界框）
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(-w/2, -h/2, w, h);

    // 绘制指甲 ID 标签
    ctx.fillStyle = color;
    ctx.fillRect(-w/2, -h/2-20, 30, 20);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(idx.toString(), -w/2+15, -h/2-10);

    // 恢复画布状态
    ctx.restore();
  });
}

// ── 用户确认检测结果 ──────────
async function confirmNailDetection() {
  const previewEl = document.getElementById('tryon-detection-preview');
  previewEl.style.display = 'none';

  const proc = document.getElementById('tryon-processing');
  proc.classList.add('show');

  // 初始化步骤
  ['ps1','ps2','ps3','ps4'].forEach(id => setStep(id, document.getElementById(id)?.textContent?.replace('✅','⏳') || '⏳', false));
  setStep('ps1', '⏳ 检测手部关键点…', false);
  setStep('ps2', '⏳ 分析肤色与手型…', false);
  setStep('ps3', '⏳ 渲染美甲效果…', false);
  setStep('ps4', '⏳ 生成 AI 分析报告…', false);

  try {
    let designImageOrId = '';
    if (isGeneratedDesign) {
      // AI 生成的设计，使用 design_id
      designImageOrId = tryonStyleInfo.designId;
      console.log('[TryOn] 即将发送 design_id:', designImageOrId, '| AI 生成款式');
      if (!designImageOrId) {
        throw new Error('AI 生成设计 ID 为空，请重新生成。');
      }
    } else {
      // 静态款式，使用 design_image
      designImageOrId = tryonStyleInfo.image || '';
      // 容错：image 为空时（如从硬编码入口进来），按款式名从 STYLES 查回 image，再用第一个款式兜底
      if (!designImageOrId && typeof STYLES !== 'undefined') {
        const fallback = STYLES.find(s => s.name === tryonStyleInfo.name && s.image) || STYLES.find(s => s.image);
        if (fallback) {
          designImageOrId = fallback.image;
          tryonStyleInfo = { ...tryonStyleInfo, image: fallback.image };
        }
      }
      console.log('[TryOn] 即将发送 design_image:', designImageOrId || '(空)', '| 款式名:', tryonStyleInfo.name);

      if (!designImageOrId) {
        throw new Error('没有选中款式（tryonStyleInfo.image 为空）。请回款式库点一个款式进试戴。');
      }
    }

    setStep('ps1', '⏳ 检测手部关键点…', false);

    // 第一阶段：skip_analysis=true，快速返回试戴图
    const data = await requestTryOn(lastTryonFile, designImageOrId, null, true);

    setStep('ps1', '✅ 手部关键点检测完成', true);
    setStep('ps2', '✅ 肤色与手型分析完成', true);
    setTimeout(() => setStep('ps3', '✅ 美甲效果渲染完成', true), 300);

    // 立即展示试戴图，不等AI分析
    setTimeout(() => {
      proc.classList.remove('show');

      if (data.success) {
        // 先展示试戴图，AI分析显示"分析中"占位
        showTryonResult(data.image_base64, null, data.n_applied);
        setStep('ps4', '⏳ AI 分析报告生成中…', false);

        // 第二阶段：异步调用AI分析，完成后更新
        _fetchAnalysisAsync(lastTryonFile, designImageOrId);
      } else {
        showFallbackResult(data.message || '未检测到手部，请重新上传');
      }
    }, 600);

  } catch (err) {
    console.error('试戴 API 失败:', err);
    setTimeout(() => {
      proc.classList.remove('show');
      showFallbackResult('后端暂时无法连接，展示模拟效果');
    }, 1000);
  }
}

// ── 异步获取AI分析 ────────────────────
async function _fetchAnalysisAsync(file, designImageOrId) {
  try {
    const formData = new FormData();
    formData.append('image', file);

    let url = `${API_BASE}/api/analyze-tryon`;
    if (isGeneratedDesign) {
      url += `?design_id=${encodeURIComponent(designImageOrId)}`;
    } else {
      url += `?design_image=${encodeURIComponent(designImageOrId)}`;
    }

    console.log('[Analysis] 开始异步AI分析...');
    const resp = await fetch(url, { method: 'POST', body: formData });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (data.success && data.analysis) {
      console.log('[Analysis] AI分析完成，更新UI');
      _updateAnalysisUI(data.analysis);
      setStep('ps4', '✅ AI 分析报告生成完成', true);
      showToast('AI分析成功 ✦');
    }
  } catch (e) {
    console.warn('[Analysis] AI分析失败:', e.message);
    setStep('ps4', '— AI 分析暂不可用', false);
  }
}

// ── 只更新AI分析UI区域 ────────────────
function _updateAnalysisUI(analysis) {
  if (!analysis) return;

  const matchScore = Math.round((analysis.confidence || 0.8) * 100);
  const el = id => document.getElementById(id);

  if (el('tryon-match-score')) el('tryon-match-score').textContent = `${matchScore}%`;
  if (el('tryon-skin-tone'))   el('tryon-skin-tone').textContent   = analysis.skin_tone   || '—';
  if (el('tryon-hand-rating')) el('tryon-hand-rating').textContent = analysis.hand_rating  || '—';
  if (el('tryon-ai-text'))     el('tryon-ai-text').textContent     = analysis.description  || '';

  if (el('rec-primary')) {
    const colors = Array.isArray(analysis.recommended_colors) ? analysis.recommended_colors.join(' · ') : '';
    el('rec-primary').textContent = colors || '—';
  }
  if (el('rec-styles')) {
    const styles = Array.isArray(analysis.style_recommendations) ? analysis.style_recommendations.join(' / ') : '';
    el('rec-styles').textContent = styles || '—';
  }

  analysisData = analysis;
}

// ── 降级模式（后端不可用时）────────────
function showFallbackResult(msg) {
  console.warn('[TryOn] 降级模式:', msg);
  document.getElementById('tryon-processing').classList.remove('show');
  document.getElementById('tryon-detection-preview').style.display = 'none';

  const emojiEl = document.getElementById('tryon-result-emoji');
  emojiEl.textContent = tryonStyleInfo.emoji;

  document.getElementById('tryon-result-label').textContent =
    `效果预览 · ${tryonStyleInfo.name}（模拟）`;

  document.getElementById('tryon-match-score').textContent = '—';
  document.getElementById('tryon-ai-text').textContent =
    msg + '。实际上线后将显示真实 AI 分析结果。';

  document.getElementById('tryon-result').classList.add('show');
  if (typeof addTryonHistory === 'function') {
    addTryonHistory({ source: '模拟试戴', matchScore: '—' });
  }
}

// ── 增强试戴效果 ────────────────────────
async function enhanceTryonEffect() {
  if (!lastTryonFile) {
    showToast('请先进行试戴');
    return;
  }

  const designImageOrId = isGeneratedDesign ? tryonStyleInfo.designId : tryonStyleInfo.image;
  if (!designImageOrId) {
    showToast('款式信息缺失');
    return;
  }

  // 显示处理中
  const enhanceBtn = document.getElementById('tryon-enhance-btn');
  const origText = enhanceBtn.textContent;
  enhanceBtn.textContent = '⏳ 增强中，请稍候...';
  enhanceBtn.disabled = true;

  try {
    // 构造FormData
    const formData = new FormData();
    formData.append('hand_image', lastTryonFile);

    // 如果是生成的设计，使用mold模式；否则尝试从款式库获取图片
    let designBlob = null;

    if (isGeneratedDesign) {
      // AI生成的设计，使用mold目录中的图片
      console.log('[Enhance] 尝试从mold目录获取AI生成设计:', designImageOrId);
      // 对于AI生成的设计，我们可能需要从后端获取或使用其他方式
      // 暂时使用一个占位符blob
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 512;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, 512, 512);
      ctx.fillStyle = '#ccc';
      ctx.font = '16px Arial';
      ctx.fillText('AI Generated Design', 50, 256);
      designBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    } else {
      // 从后端API获取款式详细图
      console.log('[Enhance] 从后端API获取款式图，designId:', designImageOrId);

      try {
        // 使用后端API获取款式图
        const apiPath = `${API_BASE}/api/design-image/${encodeURIComponent(designImageOrId)}`;
        console.log('[Enhance] 调用API:', apiPath);

        const designResponse = await fetch(apiPath);
        if (!designResponse.ok) {
          throw new Error(`HTTP ${designResponse.status}`);
        }

        designBlob = await designResponse.blob();
        console.log('[Enhance] 成功获取款式图，大小:', designBlob.size, 'bytes');

      } catch (e) {
        console.error('[Enhance] 获取款式图失败:', e);
        showToast('获取款式图失败: ' + e.message);
        enhanceBtn.textContent = origText;
        enhanceBtn.disabled = false;
        return;
      }
    }

    if (!designBlob) {
      throw new Error('未能获取款式图');
    }

    formData.append('design_image', designBlob, 'design.jpg');

    formData.append('design_name', tryonStyleInfo.name || '美甲款式');

    // 调用增强API
    console.log('[Enhance] 调用增强API...');
    const response = await fetch(`${API_BASE}/api/enhance-nail-tryon`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (data.success && data.image_base64) {
      console.log('[Enhance] 增强成功！');

      // 显示增强后的结果
      const emojiEl = document.getElementById('tryon-result-emoji');
      const baEl = document.getElementById('tryon-ba-emoji');

      if (emojiEl) {
        const imgSrc = `data:image/jpeg;base64,${data.image_base64}`;
        emojiEl.innerHTML = `<img src="${imgSrc}"
          style="width:100%;max-height:220px;object-fit:contain;border-radius:12px;" alt="增强试戴效果">`;
      }

      if (baEl) {
        const imgSrc = `data:image/jpeg;base64,${data.image_base64}`;
        baEl.innerHTML = `
          <img src="${imgSrc}"
            style="width:72px;height:72px;object-fit:cover;border-radius:10px;" alt="增强试戴效果">
          <div class="ba-label">增强效果</div>`;
      }

      showToast('✨ 增强成功！');

      // 更新标签
      const label = document.getElementById('tryon-result-label');
      if (label) {
        label.textContent = `效果预览 · ${tryonStyleInfo.name}（AI增强）`;
      }
    } else {
      showToast(data.message || '增强失败，请稍后重试');
    }

  } catch (e) {
    console.error('[Enhance] 异常:', e);
    showToast('增强失败，请稍后重试');
  } finally {
    enhanceBtn.textContent = origText;
    enhanceBtn.disabled = false;
  }
}

// ── 重置 ──────────────────────────────
function resetTryon() {
  document.getElementById('tryon-upload').style.display = 'flex';
  document.getElementById('tryon-tips').style.display = 'block';
  document.getElementById('tryon-detection-preview').style.display = 'none';
  document.getElementById('tryon-detection-buttons').style.display = 'none';
  document.getElementById('tryon-result').classList.remove('show');
  document.getElementById('tryon-processing').classList.remove('show');
  document.getElementById('tryon-file').value = '';

  // 清除之前的检测预览图和重置进度条
  const previewImg = document.getElementById('tryon-preview-image');
  if (previewImg) previewImg.src = '';

  const progressBar = document.getElementById('tryon-progress-bar');
  const progressPercent = document.getElementById('tryon-progress-percent');
  if (progressBar) progressBar.style.width = '0%';
  if (progressPercent) progressPercent.textContent = '0%';
  const progressMsg = document.getElementById('tryon-progress-message');
  if (progressMsg) progressMsg.textContent = '准备检测...';

  // 重置所有参数到默认值
  nailShape = "oval";
  nailLength = 1.0;
  nailWidth = 1.0;
  nailAngles = {
    "0": 0, "1": 0, "2": 0, "3": 0, "4": 0
  };
  lastDetectionResult = null;

  // 重置 UI 上的滑块显示（如果有的话）
  const shapeSelect = document.getElementById('nail-shape-select');
  const lengthSlider = document.getElementById('nail-length-slider');
  const widthSlider = document.getElementById('nail-width-slider');
  if (shapeSelect) shapeSelect.value = 'oval';
  if (lengthSlider) lengthSlider.value = 1.0;
  if (widthSlider) widthSlider.value = 1.0;
}

// ── 收藏 ──────────────────────────────
function saveTryonToWishlist() {
  addToWishlist(tryonStyleInfo.emoji, tryonStyleInfo.name, tryonStyleInfo.price, tryonStyleInfo.bg, tryonStyleInfo.image);
  showToast('已保存到收藏 ✓');
}

// ── 页面切换时检查生成的设计 ──────────
// Defer the patch so other scripts have had a chance to define window.go first.
window.addEventListener('DOMContentLoaded', function() {
  const originalGo = window.go;
  window.go = function(screenId) {
    if (screenId === 's-tryon') {
      initGeneratedDesignIfExists();
    }
    if (typeof originalGo === 'function') return originalGo(screenId);
    if (typeof hideAllScreens === 'function') return hideAllScreens(screenId);
  };
});
