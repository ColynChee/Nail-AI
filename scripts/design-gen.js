/* ═══════════════════════════════════════
   AI DESIGN GENERATOR
═══════════════════════════════════════ */

const DESIGN_API_BASE = 'http://localhost:8000';
let currentDesign = null;

async function generateDesign() {
  const prompt = document.getElementById('design-prompt').value.trim();

  if (!prompt) {
    showToast('请输入美甲描述 ✨');
    return;
  }

  // 显示加载状态
  const btnText = document.getElementById('gen-btn-text');
  const btn = document.querySelector('[onclick="generateDesign()"]') || document.activeElement;
  const loading = document.getElementById('gen-loading');
  const results = document.getElementById('gen-results');

  btnText.textContent = '生成中...';
  if (btn && btn.disabled !== undefined) btn.disabled = true;
  loading.style.display = 'block';
  results.style.display = 'none';
  currentDesign = null;

  try {
    const response = await fetch(`${DESIGN_API_BASE}/api/generate-nail-design?prompt=${encodeURIComponent(prompt)}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      showToast(data.error || '设计生成失败，请重试');
      return;
    }

    // 存储当前设计
    currentDesign = {
      id: data.design_id,
      preview: `${DESIGN_API_BASE}${data.preview_url}`,
      prompt: data.prompt,
      optimized: data.optimized
    };

    // 显示预览结果
    showDesignPreview();
    showToast('设计已生成，请确认 ✨');

  } catch (error) {
    console.error('[DesignGen] Error:', error);
    showToast('生成失败，请检查后端连接');
  } finally {
    btnText.textContent = '生成设计 →';
    btn.disabled = false;
    loading.style.display = 'none';
  }
}

function showDesignPreview() {
  const results = document.getElementById('gen-results');

  if (!currentDesign) return;

  results.innerHTML = `
    <div style="text-align:center">
      <!-- 预览图 -->
      <div style="margin-bottom:16px">
        <img src="${currentDesign.preview}" alt="设计预览" style="width:100%;max-height:300px;object-fit:contain;border-radius:var(--rMd);border:1px solid var(--border)">
      </div>

      <!-- 设计描述 -->
      <div style="text-align:left;margin-bottom:16px;padding:12px;background:var(--orange-light);border-radius:var(--rMd)">
        <div style="font-size:12px;color:var(--text-soft);margin-bottom:4px">设计描述</div>
        <div style="font-size:13px;color:var(--text-dark);line-height:1.6">${currentDesign.prompt}</div>
      </div>

      <!-- 操作按钮 -->
      <div style="display:flex;gap:8px">
        <button class="btn-primary" style="flex:1" onclick="confirmDesign()">确认使用 →</button>
        <button style="flex:1;padding:10px;border:1px solid var(--border);background:var(--white);color:var(--text-dark);border-radius:var(--rMd);cursor:pointer" onclick="document.getElementById('design-prompt').focus()">重新生成</button>
      </div>
    </div>
  `;

  results.style.display = 'block';
}

async function confirmDesign() {
  if (!currentDesign) return;

  const results = document.getElementById('gen-results');
  results.innerHTML = '<div style="text-align:center;color:var(--text-soft)"><div class="loading-spinner" style="margin:16px auto"></div><div style="font-size:12px;margin-top:8px">处理设计中，生成试戴模具...</div></div>';

  try {
    const response = await fetch(`${DESIGN_API_BASE}/api/confirm-nail-design?design_id=${encodeURIComponent(currentDesign.id)}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      showToast(data.error || '设计处理失败');
      results.innerHTML = '';
      return;
    }

    // 存储设计信息供试戴使用
    sessionStorage.setItem('selectedGeneratedDesign', JSON.stringify({
      id: data.design_id,
      prompt: currentDesign.prompt,
      thumbnail: data.thumbnail_url
    }));

    showToast('设计已确认，准备试戴... ✨');

    // 延迟跳转
    setTimeout(() => {
      go('s-tryon');
    }, 500);

  } catch (error) {
    console.error('[DesignGen] Confirm error:', error);
    showToast('处理失败，请重试');
    results.innerHTML = '';
  }
}
