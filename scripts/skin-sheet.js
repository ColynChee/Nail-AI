/* ══════════════════════════════════
   SKIN MATCHING
══════════════════════════════════ */
const SKIN_ANALYSIS_ENDPOINT = (window.SKIN_ANALYSIS_ENDPOINT || '').trim();

let pendingSkinMatch = null;

function openSkinSheet() {
  syncSkinSheetState();
  document.getElementById('skin-overlay').classList.add('show');
}

function closeSkinSheet() {
  document.getElementById('skin-overlay').classList.remove('show');
}

function openSkinCameraPicker() {
  const input = document.getElementById('skin-camera-input');
  if (input) input.click();
}

function openSkinUploadPicker() {
  const input = document.getElementById('skin-upload-input');
  if (input) input.click();
}

function selectSkin(item) {
  if (!item) return;
  const code = item.dataset.code || '#F5C6A0';
  const label = item.dataset.label || '自然色';
  pendingSkinMatch = {
    code: typeof normalizeHexColor === 'function' ? (normalizeHexColor(code) || '#F5C6A0') : '#F5C6A0',
    label,
    source: 'preset',
    previewUrl: '',
    message: '已选择手动肤色预设',
  };
  syncSkinSheetState();
}

function syncSkinSheetState() {
  const skinCodeNode = document.getElementById('skin-analysis-code');
  const skinLabelNode = document.getElementById('skin-analysis-label');
  const skinStatusNode = document.getElementById('skin-analysis-status');
  const skinPreviewNode = document.getElementById('skin-preview-image');
  const skinPlaceholderNode = document.getElementById('skin-preview-placeholder');
  const skinSaveBtn = document.getElementById('skin-save-btn');

  const currentCode = typeof normalizeHexColor === 'function'
    ? (pendingSkinMatch?.code || normalizeHexColor(userProfile.skinColorCode) || '#F5C6A0')
    : (pendingSkinMatch?.code || userProfile.skinColorCode || '#F5C6A0');
  const currentLabel = pendingSkinMatch?.label || userProfile.skinToneLabel || '自然色';

  if (skinCodeNode) skinCodeNode.textContent = currentCode;
  if (skinLabelNode) skinLabelNode.textContent = currentLabel;
  if (skinStatusNode) {
    const sourceLabel = pendingSkinMatch?.source === 'camera'
      ? '拍照分析'
      : pendingSkinMatch?.source === 'upload'
        ? '上传分析'
        : pendingSkinMatch?.source === 'api'
          ? 'LLM 分析'
          : '手动预设';
    skinStatusNode.textContent = pendingSkinMatch
      ? `${sourceLabel}完成`
      : `当前使用 ${currentLabel} · ${currentCode}`;
  }

  if (skinPreviewNode && skinPlaceholderNode) {
    if (pendingSkinMatch?.previewUrl) {
      skinPreviewNode.src = pendingSkinMatch.previewUrl;
      skinPreviewNode.style.display = 'block';
      skinPlaceholderNode.style.display = 'none';
    } else {
      skinPreviewNode.removeAttribute('src');
      skinPreviewNode.style.display = 'none';
      skinPlaceholderNode.style.display = 'flex';
      skinPlaceholderNode.textContent = pendingSkinMatch
        ? `已提取 ${currentCode}`
        : '拍照或上传一张自拍/手部照片';
    }
  }

  if (skinSaveBtn) skinSaveBtn.textContent = pendingSkinMatch ? '保存肤色' : '使用当前肤色';

  document.querySelectorAll('.skin-item').forEach(item => {
    const itemCode = item.dataset.code || '';
    const normalizedItemCode = typeof normalizeHexColor === 'function' ? normalizeHexColor(itemCode) : itemCode;
    const currentSavedCode = typeof normalizeHexColor === 'function'
      ? (normalizeHexColor(userProfile.skinColorCode) || '#F5C6A0')
      : (userProfile.skinColorCode || '#F5C6A0');
    const isActive = pendingSkinMatch
      ? normalizedItemCode && normalizedItemCode === currentCode
      : normalizedItemCode && normalizedItemCode === currentSavedCode;
    item.classList.toggle('on', Boolean(isActive));
  });
}

async function handleSkinImageSelection(input, source) {
  const file = input && input.files ? input.files[0] : null;
  if (!file) return;

  const statusNode = document.getElementById('skin-analysis-status');
  if (statusNode) statusNode.textContent = '正在分析肤色...';

  try {
    const analysis = await analyzeSkinImage(file, source);
    pendingSkinMatch = analysis;
    syncSkinSheetState();
    showToast(`已识别肤色 ${analysis.code}`);
  } catch (error) {
    console.error('[Skin] analyze error:', error);
    showToast('肤色分析失败，请重试');
    if (statusNode) statusNode.textContent = '分析失败';
  } finally {
    input.value = '';
  }
}

async function analyzeSkinImage(file, source) {
  try {
    const apiResult = await analyzeSkinImageViaApi(file, source);
    if (apiResult && apiResult.code) {
      return {
        ...apiResult,
        source: 'api',
        previewUrl: apiResult.previewUrl || await readFileAsDataUrl(file),
        message: apiResult.message || 'LLM 已完成肤色分析',
      };
    }
  } catch (error) {
    console.warn('[Skin] API 分析不可用，启用本地分析:', error.message);
  }

  return analyzeSkinImageLocally(file, source);
}

async function analyzeSkinImageViaApi(file, source) {
  if (!SKIN_ANALYSIS_ENDPOINT) {
    throw new Error('未配置肤色分析接口');
  }

  const formData = new FormData();
  formData.append('image', file);
  formData.append('source', source || 'upload');

  const response = await fetch(SKIN_ANALYSIS_ENDPOINT, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const data = await response.json();
  if (!data || !data.code) {
    throw new Error('缺少肤色 code');
  }

  return {
    code: typeof normalizeHexColor === 'function' ? (normalizeHexColor(data.code) || data.code) : data.code,
    label: data.label || data.tone || '自然色',
    previewUrl: data.previewUrl || data.image || '',
    confidence: data.confidence,
    message: data.message || '分析完成',
  };
}

async function analyzeSkinImageLocally(file, source) {
  const dataUrl = await readFileAsDataUrl(file);
  const image = await loadImageFromDataUrl(dataUrl);
  const canvas = document.createElement('canvas');
  const maxSide = 160;
  const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
  canvas.width = Math.max(1, Math.round(image.width * scale));
  canvas.height = Math.max(1, Math.round(image.height * scale));

  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

  const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const xStart = Math.floor(width * 0.2);
  const xEnd = Math.ceil(width * 0.8);
  const yStart = Math.floor(height * 0.2);
  const yEnd = Math.ceil(height * 0.8);

  let red = 0;
  let green = 0;
  let blue = 0;
  let count = 0;

  for (let y = yStart; y < yEnd; y += 2) {
    for (let x = xStart; x < xEnd; x += 2) {
      const idx = (y * width + x) * 4;
      const r = data[idx];
      const g = data[idx + 1];
      const b = data[idx + 2];
      const a = data[idx + 3];
      if (a < 32) continue;

      const brightness = (r + g + b) / 3;
      if (brightness < 30 || brightness > 245) continue;

      red += r;
      green += g;
      blue += b;
      count += 1;
    }
  }

  if (!count) {
    const fallback = getCenterPixelColor(data, width, height);
    red = fallback.r;
    green = fallback.g;
    blue = fallback.b;
    count = 1;
  }

  const code = rgbToHex({
    r: Math.round(red / count),
    g: Math.round(green / count),
    b: Math.round(blue / count),
  });
  const skinProfile = typeof getSkinToneProfile === 'function'
    ? getSkinToneProfile(code)
    : { code, label: '自然色' };

  return {
    code: skinProfile.code || code,
    label: skinProfile.label || '自然色',
    previewUrl: dataUrl,
    source: source || 'upload',
    message: '本地分析完成',
  };
}

function getCenterPixelColor(data, width, height) {
  const centerX = Math.floor(width / 2);
  const centerY = Math.floor(height / 2);
  const idx = (centerY * width + centerX) * 4;
  return {
    r: data[idx] || 0,
    g: data[idx + 1] || 0,
    b: data[idx + 2] || 0,
  };
}

function rgbToHex({ r, g, b }) {
  const toHex = value => Math.max(0, Math.min(255, value)).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase();
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('读取图片失败'));
    reader.readAsDataURL(file);
  });
}

function loadImageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('图片加载失败'));
    image.src = dataUrl;
  });
}

function saveSkinAnalysis() {
  const current = pendingSkinMatch || {
    code: typeof normalizeHexColor === 'function' ? (normalizeHexColor(userProfile.skinColorCode) || '#F5C6A0') : (userProfile.skinColorCode || '#F5C6A0'),
    label: userProfile.skinToneLabel || '自然色',
    source: userProfile.skinToneSource || 'preset',
  };

  userProfile = {
    ...userProfile,
    skinColorCode: typeof normalizeHexColor === 'function' ? (normalizeHexColor(current.code) || '#F5C6A0') : (current.code || '#F5C6A0'),
    skinToneLabel: current.label || '自然色',
    skinToneSource: current.source || 'preset',
  };

  saveProfileState();
  if (typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(error => console.warn('[Profile] skin sync failed:', error.message));
  }
  pendingSkinMatch = null;
  applyProfile();
  syncSkinSheetState();
  closeSkinSheet();
  showToast('肤色已保存 ✓');
}

function selectSkinPreset(code, label) {
  pendingSkinMatch = {
    code: typeof normalizeHexColor === 'function' ? (normalizeHexColor(code) || '#F5C6A0') : (code || '#F5C6A0'),
    label: label || '自然色',
    source: 'preset',
    previewUrl: '',
    message: '已选择肤色预设',
  };
  syncSkinSheetState();
}

function getSkinPresetData() {
  return [
    { code: '#FFE0C2', label: '暖白色' },
    { code: '#F5C6A0', label: '自然色' },
    { code: '#D4956A', label: '小麦色' },
    { code: '#A0724A', label: '健康棕' },
  ];
}

