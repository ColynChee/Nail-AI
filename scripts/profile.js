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

  document.getElementById('home-hello').textContent = `下午好，${name} ✨`;
  document.getElementById('home-avatar').textContent = avatar;
  document.getElementById('profile-avatar').textContent = avatar;
  document.getElementById('profile-name').textContent = name;
  document.getElementById('profile-sub').textContent = `${bio} · 已试戴 ${userProfile.tryonCount} 款`;
  document.getElementById('profile-tryon-count').textContent = userProfile.tryonCount;
  document.getElementById('profile-booking-count').textContent = userProfile.bookingCount;
  updateProfileCounts();
}

function updateProfileCounts() {
  const c = wishlist.length;
  document.getElementById('profile-wl-count').textContent = c;
  document.getElementById('profile-wl-badge').textContent = c;
}

function openProfileEditor() {
  document.getElementById('profile-name-input').value = userProfile.name || '';
  document.getElementById('profile-avatar-input').value = getProfileAvatarText();
  document.getElementById('profile-bio-input').value = userProfile.bio || '';
  document.getElementById('profile-edit-overlay').classList.add('show');
}

function closeProfileEditor() {
  document.getElementById('profile-edit-overlay').classList.remove('show');
}

function saveProfileEditor() {
  const name = document.getElementById('profile-name-input').value.trim();
  const avatar = document.getElementById('profile-avatar-input').value.trim();
  const bio = document.getElementById('profile-bio-input').value.trim();

  if (!name) {
    showToast('请先填写昵称');
    return;
  }

  userProfile = {
    ...userProfile,
    name,
    avatar: avatar || name.slice(0, 1),
    bio: bio || '美甲爱好者'
  };
  saveProfileState();
  applyProfile();
  closeProfileEditor();
  showToast('资料已保存');
}
