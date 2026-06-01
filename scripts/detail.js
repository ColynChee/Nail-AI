/* ══════════════════════════════════
   DETAIL
══════════════════════════════════ */
function goDetail(emoji, name, sub, price, bg, image, designId = null) {
  currentDetail = { emoji, name, price, bg, image, designId };
  prevScreen = document.querySelector('.screen.active').id;
  const detailImage = document.getElementById('d-image');
  const detailEmoji = document.getElementById('d-emoji');
  if (image) {
    detailImage.src = image;
    detailImage.alt = name;
    detailImage.classList.add('show');
  } else {
    detailImage.removeAttribute('src');
    detailImage.alt = '';
    detailImage.classList.remove('show');
    detailEmoji.textContent = emoji;
  }
  document.getElementById('d-name').textContent = name;
  document.getElementById('d-price').textContent = price;
  document.getElementById('d-tag1').textContent = sub.split('·')[0].trim();
  document.getElementById('detail-hero-bg').style.background = bg || 'var(--cream)';

  // 显示详细设计图（优先用 designId，其次查找 STYLES）
  let design = null;
  if (designId) {
    design = STYLES.find(d => d.id === designId);
  }
  if (!design) {
    design = STYLES.find(d => d.name === name);
  }
  const detailedImgBox = document.getElementById('d-detailed-img-box');
  const detailedImg = document.getElementById('d-detailed-img');

  console.log('[Detail] 寻找款式:', name);
  console.log('[Detail] 找到的设计:', design);
  console.log('[Detail] 详细图盒子:', detailedImgBox);

  if (design && design.detailed_image) {
    console.log('[Detail] 显示详细图:', design.detailed_image);
    detailedImg.src = design.detailed_image;
    detailedImgBox.style.display = 'block';
  } else {
    console.log('[Detail] 未找到详细图');
    detailedImgBox.style.display = 'none';
  }

  // check if in wishlist
  const inWl = wishlist.find(w => w.name === name);
  const btn = document.getElementById('d-fav-btn');
  btn.classList.toggle('liked', !!inWl);
  go('s-detail');
}

function toggleDetailFav() {
  const btn = document.getElementById('d-fav-btn');
  btn.classList.toggle('liked');
  if (btn.classList.contains('liked')) {
    addToWishlist(currentDetail.emoji, currentDetail.name, currentDetail.price, currentDetail.bg, currentDetail.image);
    showToast('已添加到收藏 ♥');
  } else {
    wishlist = wishlist.filter(w => w.name !== currentDetail.name);
    saveWishlistState();
    updateProfileCounts();
    showToast('已移出收藏');
  }
}

function pickColor(dot) {
  document.querySelectorAll('.c-dot').forEach(d => d.classList.remove('on'));
  dot.classList.add('on');
}

