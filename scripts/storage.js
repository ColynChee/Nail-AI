/* ══════════════════════════════════
   本地保存
══════════════════════════════════ */
const STORAGE_KEYS = {
  wishlist: 'nailai-wishlist',
  profile: 'nailai-profile',
  clientId: 'nailai-client-id',
  bookings: 'nailai-bookings',
  tryonHistory: 'nailai-tryon-history',
  imageTryonHistory: 'nailai-image-tryon-history',
  session: 'nailai-session'
};

// ── 登录会话 ──
function getSession() {
  const s = readStorage(STORAGE_KEYS.session, null);
  return (s && s.client_id) ? s : null;
}

function setSession(obj) {
  writeStorage(STORAGE_KEYS.session, obj);
  if (obj && obj.client_id) window.userClientId = obj.client_id;
}

function clearSession() {
  try { localStorage.removeItem(STORAGE_KEYS.session); } catch (e) {}
  window.userClientId = null;
}

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    showToast('本地保存失败，请检查浏览器权限');
  }
}

function getOrCreateClientId() {
  const existing = readStorage(STORAGE_KEYS.clientId, '');
  if (existing && typeof existing === 'string') {
    return existing;
  }

  const generated = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `client_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  writeStorage(STORAGE_KEYS.clientId, generated);
  return generated;
}

function loadPersistedState() {
  window.userClientId = getOrCreateClientId();

  const savedWishlist = readStorage(STORAGE_KEYS.wishlist, null);
  if (Array.isArray(savedWishlist)) wishlist = savedWishlist;

  const savedProfile = readStorage(STORAGE_KEYS.profile, null);
  if (savedProfile && typeof savedProfile === 'object') {
    userProfile = { ...userProfile, ...savedProfile };
  }

  const savedBookings = readStorage(STORAGE_KEYS.bookings, null);
  if (Array.isArray(savedBookings)) bookings = savedBookings;

  const savedTryonHistory = readStorage(STORAGE_KEYS.tryonHistory, null);
  if (Array.isArray(savedTryonHistory)) tryonHistory = savedTryonHistory;

  const savedImageTryonHistory = readStorage(STORAGE_KEYS.imageTryonHistory, null);
  if (Array.isArray(savedImageTryonHistory)) imageTryonHistory = savedImageTryonHistory;

  userProfile.bookingCount = bookings.length;
  userProfile.tryonCount = tryonHistory.length;
}

function saveWishlistState() {
  writeStorage(STORAGE_KEYS.wishlist, wishlist);
}

function saveProfileState() {
  writeStorage(STORAGE_KEYS.profile, userProfile);
  if (typeof syncProfileToBackend === 'function') {
    syncProfileToBackend().catch(error => console.warn('[Profile] backend sync failed:', error.message));
  }
}

async function loadProfileFromBackend() {
  const clientId = window.userClientId || getOrCreateClientId();
  try {
    const response = await fetch(`http://localhost:8000/api/profile?client_id=${encodeURIComponent(clientId)}`, { cache: 'no-store' });
    if (!response.ok) return null;
    const data = await response.json();
    const profile = data && data.profile ? data.profile : null;
    if (profile && typeof profile === 'object') {
      userProfile = { ...userProfile, ...profile };
      writeStorage(STORAGE_KEYS.profile, userProfile);
      return userProfile;
    }
  } catch (error) {
    console.warn('[Profile] backend load failed:', error.message);
  }
  return null;
}

async function syncProfileToBackend() {
  const clientId = window.userClientId || getOrCreateClientId();
  const payload = {
    client_id: clientId,
    name: userProfile.name,
    avatar: userProfile.avatar,
    age: userProfile.age,
    bio: userProfile.bio,
    skin_color_code: userProfile.skinColorCode,
    skin_tone_label: userProfile.skinToneLabel,
    skin_tone_source: userProfile.skinToneSource,
    recommended_style_ids: typeof getRecommendedStyles === 'function'
      ? getRecommendedStyles().map(item => item.id).filter(Boolean)
      : (userProfile.recommendedStyleIds || []),
  };

  const response = await fetch('http://localhost:8000/api/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const data = await response.json();
  if (data && data.profile && typeof data.profile === 'object') {
    userProfile = { ...userProfile, ...data.profile };
    writeStorage(STORAGE_KEYS.profile, userProfile);
  }
  return data;
}

function saveBookingState() {
  userProfile.bookingCount = bookings.length;
  writeStorage(STORAGE_KEYS.bookings, bookings);
  writeStorage(STORAGE_KEYS.profile, userProfile);
}

function saveTryonHistoryState() {
  userProfile.tryonCount = tryonHistory.length;
  writeStorage(STORAGE_KEYS.tryonHistory, tryonHistory);
  writeStorage(STORAGE_KEYS.profile, userProfile);
}

function saveImageTryonHistoryState() {
  writeStorage(STORAGE_KEYS.imageTryonHistory, imageTryonHistory);
}
