/* ══════════════════════════════════
   本地保存
══════════════════════════════════ */
const STORAGE_KEYS = {
  wishlist: 'nailai-wishlist',
  profile: 'nailai-profile',
  bookings: 'nailai-bookings',
  tryonHistory: 'nailai-tryon-history',
  imageTryonHistory: 'nailai-image-tryon-history'
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
