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
  document.getElementById('profile-wl-count').textContent = c;
  document.getElementById('profile-wl-badge').textContent = c;
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
