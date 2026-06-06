/* ══════════════════════════════════
   我的设计 (My Designs)
══════════════════════════════════ */
const MD_API_BASE = window.API_BASE;

let myDesigns = [];
let _mdEditingId = null;       // 正在编辑的款式 id（null = 新增）
let _mdPendingImage = null;    // 新增时待保存的 dataURL

function mdClientId() {
  return window.userClientId || (typeof getOrCreateClientId === 'function' ? getOrCreateClientId() : '');
}

// ── Tab 切换 ──────────────────────────
function switchCollectionTab(tab) {
  const isWish = tab === 'wishlist';
  document.getElementById('coll-tab-wishlist').classList.toggle('active', isWish);
  document.getElementById('coll-tab-mydesigns').classList.toggle('active', !isWish);
  document.getElementById('tab-wishlist').style.display = isWish ? 'block' : 'none';
  document.getElementById('tab-mydesigns').style.display = isWish ? 'none' : 'block';
  if (isWish) {
    renderWishlist();
  } else {
    loadMyDesigns();
  }
}

// ── 加载 / 渲染 ────────────────────────
async function loadMyDesigns() {
  const grid = document.getElementById('mydesigns-grid');
  const empty = document.getElementById('mydesigns-empty');
  try {
    const res = await fetch(`${MD_API_BASE}/api/user-designs?client_id=${encodeURIComponent(mdClientId())}`);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    myDesigns = data.designs || [];
  } catch (e) {
    console.warn('[MyDesigns] 加载失败:', e.message);
    myDesigns = [];
  }
  renderMyDesigns();
}

function renderMyDesigns() {
  const grid = document.getElementById('mydesigns-grid');
  const empty = document.getElementById('mydesigns-empty');
  if (!grid) return;
  if (!myDesigns.length) {
    grid.innerHTML = '';
    if (empty) empty.style.display = 'flex';
    return;
  }
  if (empty) empty.style.display = 'none';
  grid.innerHTML = myDesigns.map(d => {
    const img = _mdResolveImg(d.image_url);
    const canTryon = d.design_id && (d.design_id.startsWith('gen_') || d.design_id.startsWith('insp_'));
    return `
      <div class="wl-card card-press">
        <div class="wl-thumb" style="background:#FFF0F5" onclick="openDesignEdit(${d.id})">
          ${img ? `<img src="${img}" alt="${d.name}">` : '✨'}
        </div>
        <div class="wl-info">
          <div class="wl-name">${d.name || '我的设计'}</div>
          <div class="wl-row">
            ${canTryon ? `<button class="wl-try" onclick="event.stopPropagation();tryonFromMyDesign(${d.id})">试戴</button>` : '<span style="font-size:11px;color:var(--text-soft)">已保存</span>'}
            <button class="wl-del" onclick="event.stopPropagation();openDesignEdit(${d.id})" title="编辑">✎</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

// 解析我的设计图片：base64/http 原样；后端相对路径补 API_BASE
function _mdResolveImg(url) {
  if (!url) return '';
  if (url.startsWith('data:') || url.startsWith('http')) return url;
  return MD_API_BASE + url;
}

// 从「我的设计」重新试戴
function tryonFromMyDesign(id) {
  const d = myDesigns.find(x => x.id === id);
  if (!d) return;
  if (!d.design_id) {
    if (typeof showToast === 'function') showToast('该款式不支持试戴');
    return;
  }
  if (typeof setTryonStyle === 'function') {
    setTryonStyle('✨', d.name || '我的设计', 0, '#FFF9E6', _mdResolveImg(d.image_url), d.design_id);
  }
  if (typeof go === 'function') go('s-tryon');
  if (typeof showToast === 'function') showToast('请上传手部照片开始试戴 ✨');
}

// ── 上传流程 ──────────────────────────
function startDesignUpload() {
  const input = document.getElementById('md-upload-input');
  if (!input) return;
  input.value = '';
  input.onchange = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const dataUrl = ev.target.result;
      await analyzeAndOpenSheet(file, dataUrl);
    };
    reader.readAsDataURL(file);
  };
  input.click();
}

async function analyzeAndOpenSheet(file, dataUrl) {
  _mdEditingId = null;
  _mdPendingImage = dataUrl;
  // 先打开 sheet 显示 loading
  openDesignSheet({ name: '', style: '', scenes: [], description: '' }, dataUrl, false);
  const saveBtn = document.getElementById('md-btn-save');
  if (saveBtn) { saveBtn.textContent = '分析中…'; saveBtn.disabled = true; }

  try {
    const fd = new FormData();
    fd.append('image', file);
    const res = await fetch(`${MD_API_BASE}/api/analyze-design`, { method: 'POST', body: fd });
    if (res.ok) {
      const a = await res.json();
      document.getElementById('md-field-name').value = a.name || '';
      document.getElementById('md-field-style').value = a.style || '';
      document.getElementById('md-field-scenes').value = (a.scenes || []).join(', ');
      document.getElementById('md-field-desc').value = a.description || '';
      _mdPendingAnalysis = a;
      if (typeof showToast === 'function') showToast('AI 分析完成 ✨');
    } else if (res.status === 503) {
      if (typeof showToast === 'function') showToast('未配置分析模型，请手动填写');
    } else {
      if (typeof showToast === 'function') showToast('分析失败，请手动填写');
    }
  } catch (e) {
    console.warn('[MyDesigns] 分析失败:', e.message);
    if (typeof showToast === 'function') showToast('分析失败，请手动填写');
  } finally {
    if (saveBtn) { saveBtn.textContent = '保存'; saveBtn.disabled = false; }
  }
}

let _mdPendingAnalysis = null;

// ── 编辑流程 ──────────────────────────
function openDesignEdit(id) {
  const d = myDesigns.find(x => x.id === id);
  if (!d) return;
  _mdEditingId = id;
  _mdPendingImage = null;
  _mdPendingAnalysis = null;
  const img = d.image_url ? `${MD_API_BASE}${d.image_url}` : '';
  openDesignSheet(d, img, true);
}

function openDesignSheet(d, imgUrl, isEdit) {
  document.getElementById('md-field-name').value = d.name || '';
  document.getElementById('md-field-style').value = d.style || '';
  document.getElementById('md-field-scenes').value = (d.scenes || []).join(', ');
  document.getElementById('md-field-desc').value = d.description || '';
  const preview = document.getElementById('md-sheet-preview');
  preview.innerHTML = imgUrl ? `<img src="${imgUrl}" alt="预览">` : '';
  document.getElementById('md-btn-delete').style.display = isEdit ? 'block' : 'none';
  document.getElementById('md-sheet').classList.add('show');
  document.getElementById('md-sheet-overlay').classList.add('show');
}

function closeDesignSheet() {
  document.getElementById('md-sheet').classList.remove('show');
  document.getElementById('md-sheet-overlay').classList.remove('show');
}

function _collectSheetFields() {
  const scenes = document.getElementById('md-field-scenes').value
    .split(/[,，]/).map(s => s.trim()).filter(Boolean);
  return {
    name: document.getElementById('md-field-name').value.trim() || '我的设计',
    style: document.getElementById('md-field-style').value.trim(),
    scenes,
    description: document.getElementById('md-field-desc').value.trim(),
  };
}

async function saveDesignSheet() {
  const fields = _collectSheetFields();
  const saveBtn = document.getElementById('md-btn-save');
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '保存中…'; }
  try {
    if (_mdEditingId == null) {
      // 新增
      const body = {
        client_id: mdClientId(),
        source: 'upload',
        image_data: _mdPendingImage,
        ...fields,
        recommended_colors: (_mdPendingAnalysis && _mdPendingAnalysis.recommended_colors) || [],
        tags: (_mdPendingAnalysis && _mdPendingAnalysis.tags) || [],
      };
      const res = await fetch(`${MD_API_BASE}/api/user-designs`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      if (typeof showToast === 'function') showToast('已保存到我的设计 ✨');
    } else {
      // 编辑
      const res = await fetch(`${MD_API_BASE}/api/user-designs/${_mdEditingId}?client_id=${encodeURIComponent(mdClientId())}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      if (typeof showToast === 'function') showToast('已更新 ✓');
    }
    closeDesignSheet();
    await loadMyDesigns();
  } catch (e) {
    console.error('[MyDesigns] 保存失败:', e);
    if (typeof showToast === 'function') showToast('保存失败，请重试');
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '保存'; }
  }
}

async function deleteCurrentDesign() {
  if (_mdEditingId == null) return;
  try {
    const res = await fetch(`${MD_API_BASE}/api/user-designs/${_mdEditingId}?client_id=${encodeURIComponent(mdClientId())}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    if (typeof showToast === 'function') showToast('已删除');
    closeDesignSheet();
    await loadMyDesigns();
  } catch (e) {
    console.error('[MyDesigns] 删除失败:', e);
    if (typeof showToast === 'function') showToast('删除失败，请重试');
  }
}

// 供 AI 设计页 / 灵感试戴调用：保存生成的款式到「我的设计」
// img 可以是相对路径（/designs_generated/..）或 base64 data URL（灵感模具预览）
async function saveAiDesignToMine(img, name, description, designId) {
  // 前置校验：未登录直接拦截
  const cid = mdClientId();
  if (!cid) {
    if (typeof showToast === 'function') showToast('请先登录');
    return false;
  }
  if (!img) {
    if (typeof showToast === 'function') showToast('图片地址为空，保存失败');
    return false;
  }
  try {
    const body = {
      client_id: cid,
      source: 'ai',
      name: name || 'AI 生成款式',
      description: description || '',
      design_id: designId || '',
    };
    // base64 走 image_data（后端落盘），相对路径走 image_url（复用已托管图）
    if (img.startsWith('data:')) {
      body.image_data = img;
    } else {
      body.image_url = img;
    }
    const res = await fetch(`${MD_API_BASE}/api/user-designs`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!res.ok) {
      // 把后端的错误细节带出来，方便诊断（422 时 detail 是数组对象）
      let detailStr = '';
      try {
        const j = await res.json();
        const d = j.detail;
        if (typeof d === 'string') detailStr = d;
        else if (Array.isArray(d)) {
          // FastAPI 验证错误格式：[{loc:[...], msg:"...", type:"..."}]
          detailStr = d.map(x => `${(x.loc||[]).join('.')}: ${x.msg || x.type}`).join('; ');
        }
        else if (d) detailStr = JSON.stringify(d);
      } catch (e) {}
      console.error('[MyDesigns] 后端返回:', res.status, detailStr, 'body:', JSON.stringify(body));
      throw new Error(`HTTP ${res.status}${detailStr ? ' · ' + detailStr : ''}`);
    }
    if (typeof showToast === 'function') showToast('已保存到我的设计 ✨');
    // 保存成功后立即切到「我的」→ 我的设计 Tab，让用户能看到刚保存的款式
    setTimeout(() => {
      if (typeof go === 'function') go('s-wishlist');
      setTimeout(() => {
        if (typeof switchCollectionTab === 'function') switchCollectionTab('mydesigns');
      }, 100);
    }, 800);
    return true;
  } catch (e) {
    console.error('[MyDesigns] AI保存失败:', e);
    if (typeof showToast === 'function') showToast('保存失败: ' + (e.message || '未知错误'));
    return false;
  }
}
