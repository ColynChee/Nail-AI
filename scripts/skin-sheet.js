/* ══════════════════════════════════
   SKIN SHEET
══════════════════════════════════ */
function openSkinSheet() { document.getElementById('skin-overlay').classList.add('show'); }
function closeSkinSheet() { document.getElementById('skin-overlay').classList.remove('show'); }
function selectSkin(item) {
  document.querySelectorAll('.skin-item').forEach(i => i.classList.remove('on'));
  item.classList.add('on');
}

