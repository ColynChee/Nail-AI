/* ══════════════════════════════════
   IMAGE SEARCH
══════════════════════════════════ */
function runImgSearch() {
  document.getElementById('isearch-upload').style.display = 'none';
  document.getElementById('isearch-examples').style.display = 'none';
  document.getElementById('isearch-spinner').classList.add('show');
  setTimeout(() => {
    document.getElementById('isearch-spinner').classList.remove('show');
    document.getElementById('isearch-thumb').textContent = '🌸';
    document.getElementById('isearch-detected-name').textContent = '粉调花卉系 · 奶油质感';
    document.getElementById('isearch-conf').textContent = '89%';
    document.getElementById('isearch-results').classList.add('show');
  }, 2000);
}

function simulateImgSearch(emoji, name, conf) {
  document.getElementById('isearch-upload').style.display = 'none';
  document.getElementById('isearch-examples').style.display = 'none';
  document.getElementById('isearch-spinner').classList.add('show');
  setTimeout(() => {
    document.getElementById('isearch-spinner').classList.remove('show');
    document.getElementById('isearch-thumb').textContent = emoji;
    document.getElementById('isearch-detected-name').textContent = name;
    document.getElementById('isearch-conf').textContent = conf + '%';
    document.getElementById('isearch-results').classList.add('show');
  }, 1800);
}

function resetImgSearch() {
  document.getElementById('isearch-upload').style.display = 'flex';
  document.getElementById('isearch-examples').style.display = 'block';
  document.getElementById('isearch-results').classList.remove('show');
  document.getElementById('isearch-spinner').classList.remove('show');
  document.getElementById('isearch-input').value = '';
}

// ═══════════════════════════════════
// 检测美甲功能
// ═══════════════════════════════════
function switchImgTab(tab) {
  // 更新标签页样式
  document.getElementById('tab-search').classList.toggle('on', tab === 'search');
  document.getElementById('tab-detect').classList.toggle('on', tab === 'detect');

  // 显示对应区域
  document.getElementById('section-search').style.display = tab === 'search' ? 'flex' : 'none';
  document.getElementById('section-detect').style.display = tab === 'detect' ? 'flex' : 'none';
  document.getElementById('isearch-examples').style.display = tab === 'search' ? 'block' : 'none';
}

async function runDetectNails() {
  const input = document.getElementById('detect-input');
  if (!input.files.length) return;

  const file = input.files[0];
  const formData = new FormData();
  formData.append('image', file);

  // 显示加载状态
  document.getElementById('section-detect').style.display = 'none';
  document.getElementById('isearch-spinner').classList.add('show');

  try {
    const response = await fetch('http://localhost:8000/api/detect-nails-preview', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    document.getElementById('isearch-spinner').classList.remove('show');

    if (data.success) {
      // 保存原图和检测信息
      window.currentImageFile = file;
      window.currentImageData = data;

      // 显示编辑界面
      showEditorMode(data);
    } else {
      showToast(data.message || '检测失败，请重试');
      document.getElementById('section-detect').style.display = 'flex';
    }
  } catch (error) {
    console.error('[DetectNails] Error:', error);
    document.getElementById('isearch-spinner').classList.remove('show');
    showToast('检测失败，请检查后端连接');
    document.getElementById('section-detect').style.display = 'flex';
  }

  input.value = '';
}

function showEditorMode(data) {
  // 隐藏上传区域，显示检测结果面板
  document.getElementById('section-detect').style.display = 'none';

  // 显示自动检测结果和操作选项
  const resultsDiv = document.getElementById('isearch-results');
  let html = `
    <div style="padding:16px;background:var(--bg-light);border-radius:var(--rMd);margin-bottom:16px">
      <div style="font-size:13px;color:var(--text-soft);margin-bottom:12px">✅ 自动检测完成，共检测 ${data.nails_bounds?.length || 0} 个指甲</div>
      <div style="position:relative;background:white;border-radius:var(--rMd);overflow:hidden;margin-bottom:12px">
        <canvas id="preview-canvas" style="width:100%;display:block"></canvas>
      </div>
      <div style="font-size:11px;color:var(--text-soft);text-align:center">紫色框表示检测到的指甲位置</div>
    </div>

    <div style="display:flex;gap:8px;margin-bottom:16px">
      <button class="btn-primary" style="flex:1" onclick="confirmAutoDetect()">✅ 直接裁剪</button>
      <button style="flex:1;padding:10px;border:1px solid var(--border);background:var(--white);color:var(--text-dark);border-radius:var(--rMd);cursor:pointer" onclick="resetDetect()">取消</button>
    </div>
  `;

  resultsDiv.innerHTML = html;
  resultsDiv.classList.add('show');

  // 绘制预览（显示检测框）
  const img = new Image();
  img.onload = () => {
    const canvas = document.getElementById('preview-canvas');
    const container = canvas.parentElement;
    const width = container.clientWidth;
    const height = (width / img.width) * img.height;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, width, height);

    // 绘制检测框
    (data.nails_bounds || []).forEach((nail, idx) => {
      const cx = nail.cx * width;
      const cy = nail.cy * height;
      const w = nail.width * width;
      const h = nail.height * height;
      const angle = (nail.angle || 0) * Math.PI / 180;

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angle);
      ctx.strokeStyle = '#9D4EDD';
      ctx.lineWidth = 2;
      ctx.strokeRect(-w / 2, -h / 2, w, h);
      ctx.restore();
    });
  };
  img.src = data.image_data;

  window.currentEditorImage = img;
  window.currentNailsBounds = data.nails_bounds || [];
  window.currentImageData = data;
}

let editorState = {
  canvas: null,
  ctx: null,
  image: null,
  nails: [],
  selectedNail: null,
  dragHandle: null,
  isDragging: false
};

function initializeEditor(img, nailsBounds) {
  const canvas = document.getElementById('editor-canvas');
  const container = canvas.parentElement;

  // 设置 canvas 大小
  const width = container.clientWidth;
  const height = (width / img.width) * img.height;

  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext('2d');

  // 创建标记掩码 canvas（用于保存用户的标记）
  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = img.naturalWidth || img.width;
  maskCanvas.height = img.naturalHeight || img.height;

  editorState.canvas = canvas;
  editorState.ctx = ctx;
  editorState.image = img;
  editorState.maskCanvas = maskCanvas;
  editorState.maskCtx = maskCanvas.getContext('2d');
  editorState.brushColor = 'keep'; // 'keep' 或 'remove'
  editorState.brushSize = 15;
  editorState.isDrawing = false;
  editorState.scaleX = maskCanvas.width / canvas.width;
  editorState.scaleY = maskCanvas.height / canvas.height;

  // 绘制初始状态
  drawEditorCanvas();

  // 添加笔刷交互事件
  canvas.addEventListener('mousedown', handleBrushMouseDown);
  canvas.addEventListener('mousemove', handleBrushMouseMove);
  canvas.addEventListener('mouseup', handleBrushMouseUp);
  canvas.addEventListener('mouseleave', handleBrushMouseUp);
}

function drawEditorCanvas() {
  const { ctx, canvas, image, maskCanvas } = editorState;

  // 清空
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 绘制原图
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

  // 绘制用户标记（缩放到 canvas 上显示）
  if (maskCanvas && maskCanvas.width > 0) {
    ctx.globalAlpha = 0.3; // 半透明显示标记
    ctx.drawImage(maskCanvas, 0, 0, canvas.width, canvas.height);
    ctx.globalAlpha = 1.0;
  }

  // 显示笔刷预览（鼠标位置）
  if (editorState.mouseX !== undefined && editorState.mouseY !== undefined) {
    const brushColor = editorState.brushColor === 'keep' ? '#00AA00' : '#FF3333';
    ctx.strokeStyle = brushColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(editorState.mouseX, editorState.mouseY, editorState.brushSize / 2, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function handleBrushMouseDown(e) {
  editorState.isDrawing = true;
  const canvas = editorState.canvas;
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  brushDraw(x, y);
}

function handleBrushMouseMove(e) {
  const canvas = editorState.canvas;
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  // 保存鼠标位置用于显示笔刷预览
  editorState.mouseX = x;
  editorState.mouseY = y;

  if (editorState.isDrawing) {
    brushDraw(x, y);
  }

  drawEditorCanvas();
}

function handleBrushMouseUp() {
  editorState.isDrawing = false;
  drawEditorCanvas();
}

function brushDraw(canvasX, canvasY) {
  const { maskCtx, maskCanvas, image } = editorState;
  const scaleX = editorState.scaleX;
  const scaleY = editorState.scaleY;

  // 将 canvas 坐标转换到原始图片尺寸
  const maskX = canvasX * scaleX;
  const maskY = canvasY * scaleY;

  const color = editorState.brushColor === 'keep' ? '#00FF00' : '#FF0000';
  const size = editorState.brushSize;

  maskCtx.fillStyle = color;
  maskCtx.beginPath();
  maskCtx.arc(maskX, maskY, size / 2, 0, Math.PI * 2);
  maskCtx.fill();
}

async function confirmCrop() {
  const file = window.currentImageFile;
  const { maskCanvas } = editorState;

  if (!file || !maskCanvas) {
    showToast('请先标记指甲区域');
    return;
  }

  // 将标记掩码转为 base64
  const maskDataUrl = maskCanvas.toDataURL('image/png');

  // 准备数据
  const formData = new FormData();
  formData.append('image', file);
  formData.append('mask', maskDataUrl);  // 标记掩码

  document.getElementById('isearch-spinner').classList.add('show');

  try {
    const response = await fetch('http://localhost:8000/api/extract-nails-from-marking', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    document.getElementById('isearch-spinner').classList.remove('show');

    if (data.success && data.nails) {
      showDetectResults(data.nails);
      showToast('✅ 抠图完成');
    } else {
      showToast(data.message || '抠图失败');
    }
  } catch (error) {
    console.error('[ConfirmCrop] Error:', error);
    document.getElementById('isearch-spinner').classList.remove('show');
    showToast('抠图失败');
  }
}

function showDetectResults(nails) {
  // 生成裁剪结果的展示
  let html = `
    <div style="padding:16px;background:var(--bg-light);border-radius:var(--rMd);margin-bottom:16px">
      <div style="font-size:13px;color:var(--text-soft);margin-bottom:12px">✅ 检测完成，共裁剪 ${nails.length} 个指甲</div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px" id="detect-nails-grid">
  `;

  nails.forEach((nail, idx) => {
    html += `
      <div style="border-radius:8px;overflow:hidden;background:white;border:1px solid var(--border)">
        <img src="${nail}" style="width:100%;height:120px;object-fit:contain;background:white">
        <div style="padding:8px;text-align:center;font-size:12px;color:var(--text-soft)">指甲 ${idx+1}</div>
      </div>
    `;
  });

  html += `
      </div>
    </div>

    <!-- 操作按钮 -->
    <div style="display:flex;gap:8px;margin-bottom:16px">
      <button class="btn-primary" style="flex:1" onclick="confirmDetectResults()">确认使用</button>
      <button style="flex:1;padding:10px;border:1px solid var(--border);background:var(--white);color:var(--text-dark);border-radius:var(--rMd);cursor:pointer" onclick="showAdjustPanel()">调整参数</button>
    </div>

    <!-- 参数调整面板 -->
    <div id="adjust-panel" style="display:none;padding:16px;background:var(--bg-light);border-radius:var(--rMd);margin-bottom:16px">
      <div style="font-size:13px;font-weight:600;color:var(--text-dark);margin-bottom:12px">调整裁剪参数</div>

      <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-soft);display:block;margin-bottom:4px">亮度阈值: <span id="threshold-value">200</span></label>
        <input type="range" min="150" max="240" value="200" style="width:100%" oninput="updateThreshold(this.value)">
        <div style="font-size:11px;color:var(--text-soft);margin-top:4px">较低 = 保留更多细节 | 较高 = 更干净的背景</div>
      </div>

      <button class="btn-primary" style="width:100%;margin-bottom:8px" onclick="redetectWithParams()">重新裁剪</button>
      <button style="width:100%;padding:10px;border:1px solid var(--border);background:var(--white);color:var(--text-dark);border-radius:var(--rMd);cursor:pointer" onclick="hideAdjustPanel()">取消</button>
    </div>

    <!-- AI 精准裁剪选项 -->
    <button style="width:100%;padding:10px;border:1px solid var(--orange);background:var(--orange-light);color:var(--orange);border-radius:var(--rMd);cursor:pointer;font-size:12px" onclick="useVisionCropping()">📱 AI 精准裁剪（效果更好）</button>
  `;

  // 显示结果
  const resultsDiv = document.getElementById('isearch-results');
  resultsDiv.innerHTML = html;
  resultsDiv.classList.add('show');

  // 保存当前裁剪结果
  window.currentDetectNails = nails;
}

function showAdjustPanel() {
  document.getElementById('adjust-panel').style.display = 'block';
}

function hideAdjustPanel() {
  document.getElementById('adjust-panel').style.display = 'none';
}

function updateThreshold(value) {
  document.getElementById('threshold-value').textContent = value;
}

async function confirmAutoDetect() {
  // 使用自动检测结果直接裁剪
  const file = window.currentImageFile;
  const nails = window.currentNailsBounds;

  if (!file || !nails.length) {
    showToast('检测数据丢失');
    return;
  }

  // 获取原始图片尺寸
  const img = window.currentEditorImage;
  if (!img || !img.naturalWidth) {
    showToast('图片信息丢失');
    return;
  }

  const imgWidth = img.naturalWidth;
  const imgHeight = img.naturalHeight;

  const formData = new FormData();
  formData.append('image', file);

  // 转换为像素坐标（不用相对坐标）
  const crops = nails.map(nail => ({
    cx: nail.cx * imgWidth,
    cy: nail.cy * imgHeight,
    width: nail.width * imgWidth,
    height: nail.height * imgHeight,
    angle: nail.angle || 0
  }));

  console.log('[ConfirmAutoDetect] 发送裁剪参数:', crops);
  formData.append('crops', JSON.stringify(crops));

  document.getElementById('isearch-spinner').classList.add('show');

  try {
    const response = await fetch('http://localhost:8000/api/confirm-crop', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    document.getElementById('isearch-spinner').classList.remove('show');

    if (data.success && data.nails) {
      showDetectResults(data.nails);
      showToast('✅ 裁剪完成');
    } else {
      showToast(data.message || '裁剪失败');
    }
  } catch (error) {
    console.error('[ConfirmAutoDetect] Error:', error);
    document.getElementById('isearch-spinner').classList.remove('show');
    showToast('裁剪失败');
  }
}

function enterMarkingMode() {
  // 标记模式已移除
  showToast('标记模式已禁用，请使用自动检测');
}

function selectBrush(type) {
  editorState.brushColor = type;

  // 更新按钮样式
  const keepBtn = document.getElementById('brush-keep');
  const removeBtn = document.getElementById('brush-remove');

  if (type === 'keep') {
    keepBtn.style.borderColor = '#00AA00';
    keepBtn.style.background = '#E8FFE8';
    keepBtn.style.color = '#00AA00';
    removeBtn.style.borderColor = '#ddd';
    removeBtn.style.background = 'var(--white)';
    removeBtn.style.color = 'var(--text-dark)';
  } else {
    keepBtn.style.borderColor = '#ddd';
    keepBtn.style.background = 'var(--white)';
    keepBtn.style.color = 'var(--text-dark)';
    removeBtn.style.borderColor = '#FF3333';
    removeBtn.style.background = '#FFE8E8';
    removeBtn.style.color = '#FF3333';
  }

  drawEditorCanvas();
}

function changeBrushSize(value) {
  editorState.brushSize = parseInt(value);
  document.getElementById('brush-size-value').textContent = value;
  drawEditorCanvas();
}

async function redetectWithParams() {
  const threshold = document.getElementById('threshold-value').textContent;

  // 调用后端重新裁剪（传入新参数）
  const input = document.getElementById('detect-input');
  if (!input.files.length) return;

  const file = input.files[0];
  const formData = new FormData();
  formData.append('image', file);
  formData.append('brightness_threshold', threshold);

  hideAdjustPanel();
  document.getElementById('isearch-spinner').classList.add('show');

  try {
    const response = await fetch('http://localhost:8000/api/detect-nails', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    document.getElementById('isearch-spinner').classList.remove('show');

    if (data.success && data.nails && data.nails.length > 0) {
      showDetectResults(data.nails);
      showToast('重新裁剪完成');
    } else {
      showToast(data.message || '重新裁剪失败');
    }
  } catch (error) {
    console.error('[Redetect] Error:', error);
    document.getElementById('isearch-spinner').classList.remove('show');
    showToast('重新裁剪失败');
  }
}

function confirmDetectResults() {
  showToast('✅ 裁剪结果已保存');
  // 可以添加保存或使用这些裁剪结果的逻辑
  setTimeout(() => resetDetect(), 800);
}

async function useVisionCropping() {
  showToast('正在使用 AI 进行精准裁剪...');

  const input = document.getElementById('detect-input');
  if (!input.files.length) return;

  const file = input.files[0];
  const formData = new FormData();
  formData.append('image', file);

  hideAdjustPanel();
  document.getElementById('isearch-spinner').classList.add('show');

  try {
    const response = await fetch('http://localhost:8000/api/detect-nails-vision', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    document.getElementById('isearch-spinner').classList.remove('show');

    if (data.success && data.nails && data.nails.length > 0) {
      showDetectResults(data.nails);
      showToast('AI 精准裁剪完成');
    } else {
      showToast(data.message || 'AI 裁剪失败，请用参数调整试试');
    }
  } catch (error) {
    console.error('[Vision Crop] Error:', error);
    document.getElementById('isearch-spinner').classList.remove('show');
    showToast('AI 裁剪失败');
  }
}

function resetDetect() {
  document.getElementById('section-detect').style.display = 'flex';
  document.getElementById('isearch-results').classList.remove('show');
  document.getElementById('detect-input').value = '';
}

