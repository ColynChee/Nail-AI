/* ══════════════════════════════════
   本地保存
══════════════════════════════════ */
const STORAGE_KEYS = {
  wishlist: 'nailai-wishlist',
  profile: 'nailai-profile'
};

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

function loadPersistedState() {
  const savedWishlist = readStorage(STORAGE_KEYS.wishlist, null);
  if (Array.isArray(savedWishlist)) wishlist = savedWishlist;

  const savedProfile = readStorage(STORAGE_KEYS.profile, null);
  if (savedProfile && typeof savedProfile === 'object') {
    userProfile = { ...userProfile, ...savedProfile };
  }
}

function saveWishlistState() {
  writeStorage(STORAGE_KEYS.wishlist, wishlist);
}

function saveProfileState() {
  writeStorage(STORAGE_KEYS.profile, userProfile);
}
