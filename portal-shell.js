"use strict";
function toggleSidebar(force) {
  const sidebar = document.getElementById('sidebar');
  const open = typeof force === 'boolean' ? force : !sidebar.classList.contains('open');
  sidebar.classList.toggle('open', open);
  document.getElementById('sidebar-backdrop').classList.toggle('hidden', !open);
  document.getElementById('menu-button').setAttribute('aria-expanded', String(open));
}
document.addEventListener('keydown', event => { if (event.key === 'Escape') toggleSidebar(false); });
