/* ══════════════════════════════════
   TRY-ON  —  连接后端 API
══════════════════════════════════ */

// 后端地址（与 main.py 保持一致）
const API_BASE = 'http://localhost:8000';

// 缓存上传的手图与当前款式，供颜色切换复用
let lastTryonFile = null;
let currentTryonColor = null;
let isGeneratedDesign = false;  // 标记是否是 AI 生成的设计

// 甲形参数
let nailShape = "oval";     // oval / almond / square
let nailLength = 1.0;       // 0.5-1.5
let nailWidth = 1.0;        // 0.5-1.5

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

function setTryonStyle(emoji, name, price, bg, image, designId = null) {
  tryonStyleInfo = { emoji, name, price, bg, image: image || '', designId: designId || '' };
  isGeneratedDesign = !!designId;
  console.log('[TryOn] 选中款式:', name, '| image:', image || '(空)', '| designId:', designId || '(空)');
  const box = document.getElementById('tryon-thumb-box');
  if (box) {
    box.style.background = bg;

    // 显示款式图（image），不显示详细图
    const displayImage = image;

    if (displayImage) {
      box.innerHTML = `<img src="${displayImage}" alt="${name}" style="width:100%;height:100%;object-fit:cover;border-radius:var(--rMd)">`;
    } else {
      box.textContent = emoji;
    }
  }
  const lbl = document.getElementById('tryon-style-name');
  if (lbl) lbl.textContent = name;

  // 清空之前的试戴结果
  const resultEl = document.getElementById('tryon-result');
  if (resultEl) {
    const previewEmoji = document.getElementById('tryon-result-emoji');
    if (previewEmoji) previewEmoji.textContent = emoji;
    const baEmoji = document.getElementById('tryon-ba-emoji');
    if (baEmoji) baEmoji.innerHTML = `<div class="ba-emoji">${emoji}</div><div class="ba-label">试戴效果</div>`;
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
      setTryonStyle('✨', 'AI 生成款式', 0, '#FFF9E6', '', design.id);
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
function showTryonResult(imageBase64, analysisData) {
  const resultEl = document.getElementById('tryon-result');
  const emojiEl  = document.getElementById('tryon-result-emoji');
  const baEl     = document.getElementById('tryon-ba-emoji');

  console.log('[TryOn] showTryonResult 被调用，图片前50字符:', imageBase64?.substring(0, 50));

  // 显示真实图像 or emoji
  if (imageBase64) {
    console.log('[TryOn] 更新图片元素...');
    const imgSrc = `data:image/jpeg;base64,${imageBase64}`;
    emojiEl.innerHTML = `<img src="${imgSrc}"
      style="width:100%;max-height:220px;object-fit:contain;border-radius:12px;" alt="试戴效果">`;
    baEl.innerHTML = `
      <img src="${imgSrc}"
        style="width:72px;height:72px;object-fit:cover;border-radius:10px;" alt="试戴效果">
      <div class="ba-label">试戴效果</div>`;
  } else {
    emojiEl.textContent = tryonStyleInfo.emoji;
    baEl.innerHTML = `<div class="ba-emoji">${tryonStyleInfo.emoji}</div><div class="ba-label">试戴效果</div>`;
  }

  const labelSuffix = currentTryonColor ? '（换色）' : '';
  document.getElementById('tryon-result-label').textContent =
    `效果预览 · ${tryonStyleInfo.name}${labelSuffix}`;

  // 填入 AI 分析数据
  if (analysisData) {
    const confidence = analysisData.confidence
      ? Math.round(analysisData.confidence * 100) + '%'
      : '—';
    document.getElementById('tryon-match-score').textContent = confidence;
    const aiText = analysisData.description
      || `肤色：${analysisData.skin_tone || '—'}，基调：${analysisData.undertone || '—'}。推荐颜色：${(analysisData.recommended_colors || []).join('、')}`;
    document.getElementById('tryon-ai-text').textContent = aiText;
  }

  renderColorPalette();
  renderNailShapePanel();
  resultEl.classList.add('show');
}

// ── 甲形控制面板 ──────────────────────
function renderNailShapePanel() {
  let box = document.getElementById('tryon-nail-shape-panel');
  if (!box) {
    const card = document.querySelector('#tryon-result .result-preview');
    if (!card) return;
    box = document.createElement('div');
    box.id = 'tryon-nail-shape-panel';
    box.style.cssText = 'margin-top:16px;padding:12px;background:var(--bg);border-radius:var(--rMd);border:1px solid var(--border)';
    card.appendChild(box);
  } else {
    // 清除旧内容，避免重复
    box.innerHTML = '';
  }

  box.innerHTML = `
    <div style="font-size:12px;color:var(--text-soft);margin-bottom:8px">⚙️ 指甲调整</div>

    <div style="margin-bottom:10px">
      <div style="font-size:12px;color:var(--text-dark);margin-bottom:6px">形状</div>
      <div style="display:flex;gap:6px">
        <button style="flex:1;padding:8px;border:${nailShape==='oval'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:11px;cursor:pointer;font-weight:${nailShape==='oval'?'700':'400'}" onclick="updateNailShape('oval')">椭圆</button>
        <button style="flex:1;padding:8px;border:${nailShape==='almond'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:11px;cursor:pointer;font-weight:${nailShape==='almond'?'700':'400'}" onclick="updateNailShape('almond')">尖形</button>
        <button style="flex:1;padding:8px;border:${nailShape==='square'?'2px solid var(--orange)':'1px solid var(--border)'};background:var(--white);border-radius:6px;font-size:11px;cursor:pointer;font-weight:${nailShape==='square'?'700':'400'}" onclick="updateNailShape('square')">方形</button>
      </div>
    </div>

    <div style="margin-bottom:10px">
      <div style="font-size:12px;color:var(--text-dark);margin-bottom:6px">长度: <span style="color:var(--orange)">${(nailLength*100).toFixed(0)}%</span></div>
      <input type="range" min="50" max="150" value="${nailLength*100}" step="5"
        style="width:100%;height:4px;cursor:pointer"
        oninput="updateNailLength(this.value)">
    </div>

    <div>
      <div style="font-size:12px;color:var(--text-dark);margin-bottom:6px">宽度: <span style="color:var(--orange)">${(nailWidth*100).toFixed(0)}%</span></div>
      <input type="range" min="50" max="150" value="${nailWidth*100}" step="5"
        style="width:100%;height:4px;cursor:pointer"
        oninput="updateNailWidth(this.value)">
    </div>
  `;
}

function updateNailShape(shape) {
  nailShape = shape;
  // 不重新渲染面板，直接调用 applyTryonColor，它会处理所有渲染
  applyTryonColor(currentTryonColor);
}

function updateNailLength(val) {
  nailLength = parseFloat(val) / 100.0;
  // 不重新渲染面板，直接调用 applyTryonColor，它会处理所有渲染
  applyTryonColor(currentTryonColor);
}

function updateNailWidth(val) {
  nailWidth = parseFloat(val) / 100.0;
  // 不重新渲染面板，直接调用 applyTryonColor，它会处理所有渲染
  applyTryonColor(currentTryonColor);
}

// ── 颜色切换色板 ──────────────────────
function renderColorPalette() {
  let box = document.getElementById('tryon-color-palette');
  if (!box) {
    // 动态插入到结果预览卡下方
    const card = document.querySelector('#tryon-result .result-preview');
    if (!card) return;
    box = document.createElement('div');
    box.id = 'tryon-color-palette';
    box.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:12px';
    const hint = document.createElement('div');
    hint.id = 'tryon-color-hint';
    hint.textContent = '🎨 换个颜色看看哪个配你的肤色';
    hint.style.cssText = 'width:100%;text-align:center;font-size:12px;color:var(--text-mid);margin-bottom:2px';
    box.appendChild(hint);
    card.appendChild(box);
  }
  // 清掉旧色块、自定义输入（保留 hint）
  [...box.querySelectorAll('.tryon-swatch')].forEach(e => e.remove());
  [...box.querySelectorAll('[id="tryon-custom-color"]')].forEach(e => e.remove());

  TRYON_COLOR_PALETTE.forEach(c => {
    const sw = document.createElement('button');
    sw.className = 'tryon-swatch';
    const active = (currentTryonColor || '') === c.hex;
    sw.title = c.name;
    sw.onclick = () => applyTryonColor(c.hex);
    if (c.hex === '') {
      sw.textContent = '原';
      sw.style.cssText = `width:34px;height:34px;border-radius:50%;cursor:pointer;font-size:11px;
        border:${active ? '2.5px solid var(--text-dark)' : '1px solid var(--border)'};
        background:var(--white);color:var(--text-mid);font-family:inherit`;
    } else {
      sw.style.cssText = `width:34px;height:34px;border-radius:50%;cursor:pointer;background:${c.hex};
        border:${active ? '2.5px solid var(--text-dark)' : '1px solid rgba(0,0,0,.15)'}`;
    }
    box.appendChild(sw);
  });

  // 添加自定义颜色输入
  const customDiv = document.createElement('div');
  customDiv.id = 'tryon-custom-color';
  customDiv.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--border);width:100%';

  const label = document.createElement('span');
  label.textContent = '自定义';
  label.style.cssText = 'font-size:11px;color:var(--text-soft)';

  const colorInput = document.createElement('input');
  colorInput.type = 'color';
  // 确保显示当前颜色（如果没有选过颜色，显示粉色默认）
  colorInput.value = (currentTryonColor && currentTryonColor.startsWith('#')) ? currentTryonColor : '#FFC0CB';
  colorInput.style.cssText = 'width:40px;height:34px;border:1px solid var(--border);border-radius:6px;cursor:pointer';
  colorInput.onchange = (e) => {
    const newColor = e.target.value;
    console.log('[TryOn] 颜色改变:', newColor, '当前甲形:', { shape: nailShape, length: nailLength, width: nailWidth });
    applyTryonColor(newColor);
  };

  customDiv.appendChild(label);
  customDiv.appendChild(colorInput);
  box.appendChild(customDiv);
}

// 点色板或改变甲形 → 用缓存手图重新试戴（传递甲形参数）
async function applyTryonColor(hex) {
  if (!lastTryonFile) { showToast && showToast('请先上传照片试戴'); return; }
  currentTryonColor = hex || null;
  const label = document.getElementById('tryon-result-label');
  if (label) label.textContent = `效果预览 · ${tryonStyleInfo.name}（处理中…）`;
  try {
    const designImageOrId = isGeneratedDesign ? tryonStyleInfo.designId : tryonStyleInfo.image;
    const data = await requestTryOn(lastTryonFile, designImageOrId, currentTryonColor);
    console.log('[TryOn] 响应:', { success: data.success, hasImage: !!data.image_base64 });
    if (data.success) {
      console.log('[TryOn] 更新试戴结果，甲形:', { shape: nailShape, length: nailLength, width: nailWidth });
      showTryonResult(data.image_base64, data.analysis);
      renderColorPalette();  // 重新渲染色板，保持状态
      renderNailShapePanel();  // 重新渲染甲形面板，保持状态
    } else {
      console.error('[TryOn] 试戴失败:', data.message);
      showToast && showToast(data.message || '更新失败');
    }
  } catch (e) {
    console.error('[TryOn] 异常:', e);
    showToast && showToast('更新失败，请重试');
  }
}

// ── 统一的试戴请求 ────────────────────
async function requestTryOn(file, designImageOrId, color) {
  const formData = new FormData();
  formData.append('image', file);
  let url = `${API_BASE}/api/try-on`;
  if (isGeneratedDesign) {
    url += `?design_id=${encodeURIComponent(designImageOrId)}`;
  } else {
    url += `?design_image=${encodeURIComponent(designImageOrId)}`;
  }
  if (color) url += `&color=${encodeURIComponent(color)}`;
  // 添加甲形参数
  url += `&shape=${encodeURIComponent(nailShape)}`;
  url += `&length=${nailLength}`;
  url += `&width=${nailWidth}`;

  console.log('[TryOn] 请求参数:', {
    color: color,
    shape: nailShape,
    length: nailLength,
    width: nailWidth,
    url: url
  });

  const response = await fetch(url, { method: 'POST', body: formData });
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

  // 隐藏上传区域，显示进度
  document.getElementById('tryon-upload').style.display = 'none';
  document.getElementById('tryon-tips').style.display = 'none';
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

    const data = await requestTryOn(file, designImageOrId, null);

    setStep('ps1', '✅ 手部关键点检测完成', true);

    // Step 2：肤色分析
    setStep('ps2', '✅ 肤色与手型分析完成', true);

    // Step 3：渲染效果
    setTimeout(() => setStep('ps3', '✅ 美甲效果渲染完成', true), 300);

    // Step 4：生成报告
    setTimeout(() => setStep('ps4', '✅ AI 分析报告生成完成', true), 600);

    // 900ms 后显示结果
    setTimeout(() => {
      proc.classList.remove('show');

      if (data.success) {
        showTryonResult(data.image_base64, data.analysis);
      } else {
        // 后端返回失败（例如未检测到手部）
        showFallbackResult(data.message || '未检测到手部，请重新上传');
      }
    }, 900);

  } catch (err) {
    console.error('试戴 API 失败:', err);
    // 网络错误 → 降级到模拟模式
    setTimeout(() => {
      proc.classList.remove('show');
      showFallbackResult('后端暂时无法连接，展示模拟效果');
    }, 1000);
  }
}

// ── 降级模式（后端不可用时）────────────
function showFallbackResult(msg) {
  console.warn('[TryOn] 降级模式:', msg);
  const emojiEl = document.getElementById('tryon-result-emoji');
  emojiEl.textContent = tryonStyleInfo.emoji;

  document.getElementById('tryon-result-label').textContent =
    `效果预览 · ${tryonStyleInfo.name}（模拟）`;

  document.getElementById('tryon-ba-emoji').innerHTML =
    `<div class="ba-emoji">${tryonStyleInfo.emoji}</div><div class="ba-label">试戴效果</div>`;

  document.getElementById('tryon-match-score').textContent = '—';
  document.getElementById('tryon-ai-text').textContent =
    msg + '。实际上线后将显示真实 AI 分析结果。';

  document.getElementById('tryon-result').classList.add('show');
}

// ── 重置 ──────────────────────────────
function resetTryon() {
  document.getElementById('tryon-upload').style.display = 'flex';
  document.getElementById('tryon-tips').style.display = 'block';
  document.getElementById('tryon-result').classList.remove('show');
  document.getElementById('tryon-processing').classList.remove('show');
  document.getElementById('tryon-file').value = '';
}

// ── 收藏 ──────────────────────────────
function saveTryonToWishlist() {
  addToWishlist(tryonStyleInfo.emoji, tryonStyleInfo.name, tryonStyleInfo.price, tryonStyleInfo.bg, tryonStyleInfo.image);
  showToast('已保存到收藏 ✓');
}

// ── 页面切换时检查生成的设计 ──────────
(function() {
  const originalGo = window.go;
  window.go = function(screenId) {
    if (screenId === 's-tryon') {
      initGeneratedDesignIfExists();
    }
    return originalGo ? originalGo(screenId) : hideAllScreens(screenId);
  };
})();
