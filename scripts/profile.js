/* ══════════════════════════════════
   PROFILE
══════════════════════════════════ */
function getProfileAvatarText() {
  const avatar = (userProfile.avatar || '').trim();
  if (avatar) return avatar.slice(0, 2);
  return (userProfile.name || '我').trim().slice(0, 1);
}

function applyProfile() {
  const name = (userProfile.name || '小美同学').trim();
  const avatar = getProfileAvatarText();
  const bio = (userProfile.bio || '美甲爱好者').trim();
  const age = Number.isFinite(Number(userProfile.age)) ? Number(userProfile.age) : 24;
  const skinProfile = typeof getSkinToneProfile === 'function'
    ? getSkinToneProfile(userProfile.skinColorCode)
    : { code: userProfile.skinColorCode || '#F5C6A0', label: userProfile.skinToneLabel || '自然色' };
  userProfile.bookingCount = bookings.length;
  userProfile.tryonCount = tryonHistory.length;

  document.getElementById('home-hello').textContent = `下午好，${name} ✨`;
  document.getElementById('home-avatar').textContent = avatar;
  document.getElementById('profile-avatar').textContent = avatar;
  document.getElementById('profile-name').textContent = name;
  document.getElementById('profile-sub').textContent = `${age}岁 · ${skinProfile.label} · ${bio}`;
  const ageNode = document.getElementById('profile-age');
  if (ageNode) ageNode.textContent = `${age}`;
  const skinCodeNode = document.getElementById('profile-skin-code');
  if (skinCodeNode) skinCodeNode.textContent = skinProfile.code;
  const skinLabelNode = document.getElementById('profile-skin-label');
  if (skinLabelNode) skinLabelNode.textContent = skinProfile.label;
  document.getElementById('profile-tryon-count').textContent = userProfile.tryonCount;
  document.getElementById('profile-booking-count').textContent = userProfile.bookingCount;
  updateProfileCounts();
  if (typeof renderHomeRecommendations === 'function') renderHomeRecommendations();
}

function updateProfileCounts() {
  const c = wishlist.length;
  const bookingCount = bookings.length;
  const tryonCount = tryonHistory.length;
  const imageTryonCount = imageTryonHistory.length;
  document.getElementById('profile-wl-count').textContent = c;
  document.getElementById('profile-wl-badge').textContent = c;
  document.getElementById('profile-wl-badge').style.display = c ? 'inline-flex' : 'none';
  document.getElementById('profile-tryon-count').textContent = tryonCount;
  document.getElementById('profile-booking-count').textContent = bookingCount;
  setMenuBadge('profile-booking-badge', bookingCount);
  setMenuBadge('profile-imgtryon-badge', imageTryonCount);
  setMenuBadge('profile-tryon-badge', tryonCount);
}

function setMenuBadge(id, count) {
  const badge = document.getElementById(id);
  if (!badge) return;
  badge.textContent = count;
  badge.style.display = count ? 'inline-flex' : 'none';
}

function createBooking(source, style) {
  const matchedStyle = STYLES.find(s => s.id === style.designId || s.name === style.name) || {};
  return {
    id: `booking-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    designId: style.designId || matchedStyle.id || '',
    emoji: style.emoji || matchedStyle.emoji || '💅',
    name: style.name || matchedStyle.name || '美甲款式',
    price: style.price || matchedStyle.price || '—',
    bg: style.bg || matchedStyle.bg || '#FFF4F0',
    image: style.image || matchedStyle.image || '',
    source,
    status: '待联系',
    createdAt: new Date().toISOString()
  };
}

function addBooking(source, style) {
  const booking = createBooking(source, style);
  bookings = [booking, ...bookings].slice(0, 30);
  saveBookingState();
  updateProfileCounts();
  showToast('预约成功！已加入预约记录 ✓');
  return booking;
}

function bookCurrentDetail() {
  if (!currentDetail || !currentDetail.name) {
    showToast('请先选择一个款式');
    return;
  }
  addBooking('款式详情', currentDetail);
}

function bookCurrentTryon() {
  if (!tryonStyleInfo || !tryonStyleInfo.name) {
    showToast('请先选择一个试戴款式');
    return;
  }
  addBooking('AI试戴结果', tryonStyleInfo);
}

function formatBookingTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '刚刚';
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const min = String(date.getMinutes()).padStart(2, '0');
  return `${mm}/${dd} ${hh}:${min}`;
}

function openBookingRecords() {
  renderBookings();
  go('s-bookings');
}

function renderBookings() {
  const list = document.getElementById('booking-list');
  const empty = document.getElementById('booking-empty');
  if (!list || !empty) return;

  if (!bookings.length) {
    list.innerHTML = '';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  list.innerHTML = bookings.map(booking => `
    <div class="booking-card">
      <div class="booking-thumb" style="background:${booking.bg || '#FFF4F0'}">
        ${booking.image ? `<img src="${booking.image}" alt="${booking.name}">` : (booking.emoji || '💅')}
      </div>
      <div class="booking-info">
        <div class="booking-top">
          <div class="booking-name">${booking.name}</div>
          <span class="booking-status">${booking.status || '待联系'}</span>
        </div>
        <div class="booking-meta">${formatBookingTime(booking.createdAt)} · ${booking.source || '立即预约'}</div>
        <div class="booking-bottom">
          <span class="booking-price">${booking.price || '—'}</span>
          <div class="booking-actions">
            <button onclick="openBookingDetail('${booking.id}')">查看款式</button>
            <button onclick="cancelBooking('${booking.id}')">取消</button>
          </div>
        </div>
      </div>
    </div>
  `).join('');
}

function openBookingDetail(id) {
  const booking = bookings.find(item => item.id === id);
  if (!booking) return;
  goDetail(booking.emoji, booking.name, '预约记录', booking.price, booking.bg, booking.image, booking.designId);
}

function cancelBooking(id) {
  bookings = bookings.filter(item => item.id !== id);
  saveBookingState();
  renderBookings();
  updateProfileCounts();
  showToast('已取消预约');
}

function createHistoryItem(style, extra = {}) {
  const matchedStyle = STYLES.find(s => s.id === style.designId || s.name === style.name) || {};
  return {
    id: `history-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    designId: style.designId || matchedStyle.id || '',
    emoji: style.emoji || matchedStyle.emoji || '💅',
    name: style.name || matchedStyle.name || '美甲款式',
    price: style.price || matchedStyle.price || '—',
    bg: style.bg || matchedStyle.bg || '#FFF4F0',
    image: style.image || matchedStyle.image || '',
    createdAt: new Date().toISOString(),
    ...extra
  };
}

function addTryonHistory(extra = {}) {
  if (!tryonStyleInfo || !tryonStyleInfo.name) return;
  const item = createHistoryItem(tryonStyleInfo, {
    source: extra.source || 'AI试戴',
    resultImage: extra.resultImage || '',
    matchScore: extra.matchScore || document.getElementById('tryon-match-score')?.textContent || '—',
    skinTone: extra.skinTone || document.getElementById('tryon-skin-tone')?.textContent || '—',
    handRating: extra.handRating || document.getElementById('tryon-hand-rating')?.textContent || '—'
  });
  tryonHistory = [item, ...tryonHistory].slice(0, 40);
  saveTryonHistoryState();
  updateProfileCounts();
}

function addImageTryonHistory(extra = {}) {
  const item = {
    id: `image-history-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: extra.type || '以图试戴',
    title: extra.title || '图片识别结果',
    confidence: extra.confidence || '—',
    image: extra.image || '',
    resultCount: extra.resultCount || 0,
    createdAt: new Date().toISOString()
  };
  imageTryonHistory = [item, ...imageTryonHistory].slice(0, 40);
  saveImageTryonHistoryState();
  updateProfileCounts();
}

function openTryonHistory() {
  renderTryonHistory();
  go('s-tryon-history');
}

function openImageTryonHistory() {
  renderImageTryonHistory();
  go('s-imgtryon-history');
}

function renderTryonHistory() {
  renderHistoryList({
    listId: 'tryon-history-list',
    emptyId: 'tryon-history-empty',
    items: tryonHistory,
    emptyTitle: '还没有试戴记录',
    emptySub: '完成一次 AI 试戴后，结果会自动保存在这里。',
    card: item => historyStyleCard(item, 'tryon')
  });
}

function renderImageTryonHistory() {
  renderHistoryList({
    listId: 'imgtryon-history-list',
    emptyId: 'imgtryon-history-empty',
    items: imageTryonHistory,
    emptyTitle: '还没有以图试戴历史',
    emptySub: '上传灵感图或检测美甲后，记录会自动保存在这里。',
    card: item => imageHistoryCard(item)
  });
}

function renderHistoryList({ listId, emptyId, items, emptyTitle, emptySub, card }) {
  const list = document.getElementById(listId);
  const empty = document.getElementById(emptyId);
  if (!list || !empty) return;
  if (!items.length) {
    list.innerHTML = '';
    empty.innerHTML = `<div class="empty-ico">🕘</div><div class="empty-title">${emptyTitle}</div><div class="empty-sub">${emptySub}</div>`;
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';
  list.innerHTML = items.map(card).join('');
}

function historyStyleCard(item, type) {
  const thumb = item.resultImage
    ? `<img src="${item.resultImage}" alt="${item.name}">`
    : item.image
      ? `<img src="${item.image}" alt="${item.name}">`
      : (item.emoji || '💅');
  return `
    <div class="booking-card">
      <div class="booking-thumb" style="background:${item.bg || '#FFF4F0'}">${thumb}</div>
      <div class="booking-info">
        <div class="booking-top">
          <div class="booking-name">${item.name}</div>
          <span class="booking-status">${item.matchScore || '已完成'}</span>
        </div>
        <div class="booking-meta">${formatBookingTime(item.createdAt)} · ${item.source || 'AI试戴'} · ${item.skinTone || '肤色—'}</div>
        <div class="booking-bottom">
          <span class="booking-price">${item.price || '—'}</span>
          <div class="booking-actions">
            <button onclick="openHistoryStyle('${item.id}', '${type}')">查看款式</button>
            <button onclick="removeHistoryItem('${item.id}', '${type}')">删除</button>
          </div>
        </div>
      </div>
    </div>`;
}

function imageHistoryCard(item) {
  const thumb = item.image ? `<img src="${item.image}" alt="${item.title}">` : '🔍';
  return `
    <div class="booking-card">
      <div class="booking-thumb" style="background:var(--purple-light)">${thumb}</div>
      <div class="booking-info">
        <div class="booking-top">
          <div class="booking-name">${item.title}</div>
          <span class="booking-status">${item.confidence}</span>
        </div>
        <div class="booking-meta">${formatBookingTime(item.createdAt)} · ${item.type} · ${item.resultCount || 0} 个结果</div>
        <div class="booking-bottom">
          <span class="booking-price">已保存</span>
          <div class="booking-actions">
            <button onclick="go('s-imgsearch')">再次试戴</button>
            <button onclick="removeHistoryItem('${item.id}', 'image')">删除</button>
          </div>
        </div>
      </div>
    </div>`;
}

function openHistoryStyle(id, type) {
  const source = type === 'tryon' ? tryonHistory : [];
  const item = source.find(record => record.id === id);
  if (!item) return;
  goDetail(item.emoji, item.name, '试戴历史', item.price, item.bg, item.image, item.designId);
}

function removeHistoryItem(id, type) {
  if (type === 'tryon') {
    tryonHistory = tryonHistory.filter(item => item.id !== id);
    saveTryonHistoryState();
    renderTryonHistory();
  } else {
    imageTryonHistory = imageTryonHistory.filter(item => item.id !== id);
    saveImageTryonHistoryState();
    renderImageTryonHistory();
  }
  updateProfileCounts();
  showToast('记录已删除');
}

function openProfileEditor() {
  document.getElementById('profile-name-input').value = userProfile.name || '';
  document.getElementById('profile-avatar-input').value = getProfileAvatarText();
  document.getElementById('profile-age-input').value = Number.isFinite(Number(userProfile.age)) ? Number(userProfile.age) : 24;
  document.getElementById('profile-bio-input').value = userProfile.bio || '';
  document.getElementById('profile-skin-input').value = (typeof normalizeHexColor === 'function' ? normalizeHexColor(userProfile.skinColorCode) : userProfile.skinColorCode) || '#F5C6A0';
  document.getElementById('profile-edit-overlay').classList.add('show');
}

function closeProfileEditor() {
  document.getElementById('profile-edit-overlay').classList.remove('show');
}

function saveProfileEditor() {
  const name = document.getElementById('profile-name-input').value.trim();
  const avatar = document.getElementById('profile-avatar-input').value.trim();
  const ageValue = Number.parseInt(document.getElementById('profile-age-input').value, 10);
  const bio = document.getElementById('profile-bio-input').value.trim();
  const skinColorCode = document.getElementById('profile-skin-input').value.trim();

  if (!name) {
    showToast('请先填写昵称');
    return;
  }

  userProfile = {
    ...userProfile,
    name,
    avatar: avatar || name.slice(0, 1),
    age: Number.isFinite(ageValue) ? Math.max(1, Math.min(120, ageValue)) : (userProfile.age || 24),
    bio: bio || '美甲爱好者',
    skinColorCode: typeof normalizeHexColor === 'function' ? (normalizeHexColor(skinColorCode) || userProfile.skinColorCode || '#F5C6A0') : (skinColorCode || userProfile.skinColorCode || '#F5C6A0'),
    skinToneLabel: typeof getSkinToneProfile === 'function'
      ? getSkinToneProfile(skinColorCode || userProfile.skinColorCode || '#F5C6A0').label
      : (userProfile.skinToneLabel || '自然色')
  };
  saveProfileState();
  applyProfile();
  closeProfileEditor();
  showToast('资料已保存');
}

function collectProfileRecommendedStyleIds() {
  if (typeof getRecommendedStyles !== 'function') return [];
  return getRecommendedStyles().map(item => item.id).filter(Boolean);
}
