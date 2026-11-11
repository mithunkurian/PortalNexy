"use strict";
// ATLAS is a separate project from the NexyDAO journal. No broker/API connection.
let atlasLatest = null;
let atlasRefreshAttempted = false;
let atlasRefreshPending = false;
let atlasRefreshMessage = '';
const atlasMilestoneExpanded = new Map();
function validAtlasProgress(data) {
  const text = value => typeof value === 'string';
  const statuses = ['Complete', 'In progress', 'Not started'];
  return data && text(data.updated) && text(data.currentFeature) && Number.isFinite(data.budgetHours) &&
    Array.isArray(data.checks) && data.checks.every(text) && Array.isArray(data.blockers) && data.blockers.every(text) &&
    Array.isArray(data.milestones) && data.milestones.length > 0 && data.milestones.every(m =>
      m && [m.id,m.name,m.evidence,m.next].every(text) && statuses.includes(m.status) && Number.isFinite(m.budget) &&
      Array.isArray(m.features) && m.features.every(f => f && text(f.id) && text(f.name) && statuses.includes(f.status)));
}
async function refreshAtlasTracker() {
  if (atlasRefreshPending) return;
  atlasRefreshAttempted = true;
  atlasRefreshPending = true;
  const button = document.getElementById('atlas-refresh');
  if (button) { button.disabled = true; button.textContent = 'Refreshing…'; }
  try {
    const response = await fetch('https://raw.githubusercontent.com/mithunkurian/ATLAS/main/dashboard/progress.json', {
      credentials:'omit', cache:'no-store', signal:AbortSignal.timeout(8000)
    });
    if (!response.ok) throw new Error('Unavailable');
    const progress = await response.json();
    if (!validAtlasProgress(progress)) throw new Error('Invalid tracker');
    atlasLatest = {branch:'main', revision:null, progress};
    atlasRefreshMessage = `Latest status retrieved from ATLAS main at ${new Date().toLocaleString()}.`;
  } catch {
    atlasRefreshMessage = atlasLatest ? 'Refresh failed. Showing the last retrieved status; retry when connected.' :
      'Latest status unavailable. Showing the bundled snapshot; retry when connected.';
  } finally {
    atlasRefreshPending = false;
    if (location.hash === '#development-tracker') renderWorkspace();
  }
}
function atlasTrackerView() {
  const snapshot = atlasLatest || window.ATLAS_TRACKER;
  if (!snapshot || !snapshot.progress) {
    return '<section class="atlas-tracker"><h1>Development Tracker</h1><p role="alert">ATLAS snapshot unavailable. Rebuild the portal with tools/sync_atlas.py and tools/build_ui.py.</p></section>';
  }
  const data = snapshot.progress;
  const current = data.milestones.flatMap(m => m.features).find(f => f.id === data.currentFeature);
  const completed = data.milestones.filter(m => m.status === 'Complete').length;
  const href = `https://github.com/mithunkurian/ATLAS/blob/${encodeURIComponent(snapshot.revision || 'main')}/docs/development-tracker.md`;
  return `<section class="atlas-tracker" aria-labelledby="atlas-title">
    <div class="page-heading"><div><p class="eyebrow">ATLAS / PAPER-TRADING MVP</p><h1 id="atlas-title">Development Tracker</h1><p class="subtitle">Milestones, verified evidence and the next step for ATLAS.</p></div><div class="atlas-actions"><button id="atlas-refresh" class="outline-button" ${atlasRefreshPending ? 'disabled' : ''}>Refresh latest status</button>${external(href, 'Read full tracker', 'outline-button')}</div></div>
    <div class="source-line"><span>Snapshot updated ${escapeHTML(data.updated)}</span>${snapshot.revision ? `<span class="revision">${escapeHTML(snapshot.revision.slice(0, 7))}</span>` : '<span>Fetched from main</span>'}<span>Branch: ${escapeHTML(snapshot.branch)}</span></div>
    <p id="atlas-refresh-status" role="status">${escapeHTML(atlasRefreshMessage || "Showing the bundled snapshot while checking ATLAS main for updates.")}</p>
    <p class="atlas-notice">Development status only. Reads ATLAS’s public tracker from GitHub, with a bundled snapshot if unavailable. It does not monitor trading or connect to IBKR. NexyDAO’s separate record stays in Development Journal.</p>
    <div class="atlas-summary">
      <article class="panel"><span>Milestones complete</span><strong>${completed} <small>of ${data.milestones.length}</small></strong><p>Acceptance percentages count fully implemented and validated features.</p></article>
      <article class="panel"><span>Current work</span><strong>${escapeHTML(data.currentFeature)}</strong><p>${escapeHTML(current ? current.name : 'See milestone evidence')}</p></article>
      <article class="panel"><span>Engineering budget</span><strong>${escapeHTML(data.budgetHours)} <small>hours agreed</small></strong><p>Historical hours used and total remaining: unknown.</p></article>
    </div>
    <section class="panel atlas-next" aria-labelledby="atlas-next-title"><p class="eyebrow">NEXT ACCEPTANCE GATE</p><h2 id="atlas-next-title">${escapeHTML(data.currentFeature)} · ${escapeHTML(current ? current.name : 'Current work')}</h2><p>${escapeHTML(data.milestones.find(m => m.features.some(f => f.id === data.currentFeature))?.next || '')}</p><span class="atlas-badge progress">Paper development · no live-money authorization</span></section>
    <div class="atlas-layout"><section aria-labelledby="atlas-milestones-title"><div class="section-heading"><h2 id="atlas-milestones-title">Milestone metro map</h2><span id="atlas-result-count" role="status"></span></div>
      <div class="atlas-toolbar"><label for="atlas-search">Search milestones<input id="atlas-search" type="search" placeholder="Search features or evidence…"></label><label for="atlas-status">Status<select id="atlas-status"><option value="all">All statuses</option><option>In progress</option><option>Complete</option><option>Not started</option></select></label></div>
      <div class="atlas-map-tools"><div class="atlas-legend" aria-label="Map legend"><span><i class="atlas-legend-stop validated" aria-hidden="true"></i> Complete</span><span><i class="atlas-legend-stop current" aria-hidden="true"></i> Current work</span><span><i class="atlas-legend-stop" aria-hidden="true"></i> Upcoming</span></div><div><button type="button" id="atlas-expand-all">Expand all</button><button type="button" id="atlas-collapse-all">Collapse all</button></div></div>
      <div id="atlas-milestones" aria-label="Milestone metro map"></div>
    </section><aside class="atlas-aside"><section class="panel"><h2>Open gates</h2><ul>${data.blockers.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul></section>
      <section class="panel"><h2>Evidence log</h2><p class="muted">Cloud checks and user-reported VM results are identified separately.</p><details class="atlas-checks"><summary>${data.checks.length} recorded checks</summary><ol>${data.checks.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ol></details></section>
      <section class="panel"><h2>Scope stays bounded</h2><p>NASDAQ common stocks. Existing IBKR subscriptions only. No Level 2 dependency or extra paid news. Independent risk controls before orders.</p><p>Strategy and risk limits still need decisions. The planned M8 trading dashboard remains separate.</p></section>
    </aside></div>
  </section>`;
}
function atlasStatusClass(status) {
  return status === 'Complete' ? 'validated' : status === 'In progress' ? 'progress' : 'planned';
}
function bindAtlasTracker() {
  if (!window.ATLAS_TRACKER || !document.getElementById('atlas-search')) return;
  const data = (atlasLatest || window.ATLAS_TRACKER).progress;
  document.getElementById('atlas-refresh').addEventListener('click', refreshAtlasTracker);
  function render() {
    const query = document.getElementById('atlas-search').value.trim().toLowerCase();
    const status = document.getElementById('atlas-status').value;
    const milestones = data.milestones.filter(m => (status === 'all' || m.status === status) &&
      `${m.id} ${m.name} ${m.evidence} ${m.next} ${m.features.map(f => `${f.id} ${f.name}`).join(' ')}`.toLowerCase().includes(query));
    document.getElementById('atlas-result-count').textContent = `${milestones.length} of ${data.milestones.length} milestones`;
    const station = m => {
      const isCurrent = m.features.some(f => f.id === data.currentFeature);
      const expanded = atlasMilestoneExpanded.has(m.id) ? atlasMilestoneExpanded.get(m.id) : isCurrent || Boolean(query);
      const finished = m.features.filter(f => f.status === 'Complete').length;
      return `<details class="atlas-milestone ${atlasStatusClass(m.status)} ${isCurrent ? 'atlas-current-station' : ''}" data-milestone="${escapeHTML(m.id)}" ${expanded ? 'open' : ''}><summary><span class="atlas-station-node ${atlasStatusClass(m.status)} ${isCurrent ? 'current' : ''}" aria-hidden="true">${m.status === 'Complete' ? '✓' : ''}</span><span class="atlas-milestone-id">${escapeHTML(m.id)}</span><span class="atlas-milestone-name">${escapeHTML(m.name)}<small>${isCurrent ? 'Current milestone · ' : ''}${finished} / ${m.features.length} feature stops complete · ${m.features.length ? Math.round(finished / m.features.length * 100) : 0}% accepted</small></span><span class="atlas-badge ${atlasStatusClass(m.status)}">${escapeHTML(m.status)}</span></summary><div class="atlas-milestone-body"><h3>Feature stops</h3><ul class="atlas-features">${m.features.map(f => `<li class="atlas-feature ${atlasStatusClass(f.status)} ${f.id === data.currentFeature ? 'atlas-current-feature' : ''}" ${f.id === data.currentFeature ? 'aria-current="step"' : ''}><span class="atlas-feature-stop ${atlasStatusClass(f.status)} ${f.id === data.currentFeature ? 'current' : ''}" aria-hidden="true">${f.status === 'Complete' ? '✓' : ''}</span><span><b>${escapeHTML(f.id)}</b> ${escapeHTML(f.name)}</span><span class="atlas-badge ${atlasStatusClass(f.status)}">${escapeHTML(f.status)}${f.id === data.currentFeature ? ' · Current' : ''}</span></li>`).join('')}</ul><h3>Evidence</h3><p>${escapeHTML(m.evidence)}</p><h3>Next step</h3><p>${escapeHTML(m.next)}</p><p class="atlas-budget">Agreed milestone budget: ${escapeHTML(m.budget)}h · Historical used and total remaining time unknown.</p></div></details>`;
    };
    const assigned = new Set();
    const phases = (Array.isArray(data.phases) ? data.phases : []).filter(p => p && typeof p.name === 'string' && Array.isArray(p.milestones)).map(p => {
      const members = data.milestones.filter(m => p.milestones.includes(m.id) && !assigned.has(m.id));
      members.forEach(m => assigned.add(m.id));
      return {name:p.name, members};
    });
    const remaining = data.milestones.filter(m => !assigned.has(m.id));
    if (remaining.length) phases.push({name:'MVP route', members:remaining});
    const visible = new Set(milestones.map(m => m.id));
    document.getElementById('atlas-milestones').innerHTML = milestones.length ? phases.map(phase => {
      const members = phase.members.filter(m => visible.has(m.id));
      if (!members.length) return '';
      const features = phase.members.flatMap(m => m.features);
      const complete = features.filter(f => f.status === 'Complete').length;
      return `<section class="atlas-phase ${complete === features.length ? 'validated' : ''}"><h3 class="atlas-phase-title">${escapeHTML(phase.name)}<span>${complete} / ${features.length} feature stops complete</span></h3><div class="atlas-route">${members.map(station).join('')}</div></section>`;
    }).join('') : '<p class="empty-results" role="status">No milestones match. Try another search or status.</p>';
    document.querySelectorAll('.atlas-milestone').forEach(details => details.addEventListener('toggle', () => {
      if (details.isConnected) atlasMilestoneExpanded.set(details.dataset.milestone, details.open);
    }));
  }
  document.getElementById('atlas-expand-all').addEventListener('click', () => {
    data.milestones.forEach(m => atlasMilestoneExpanded.set(m.id, true));
    render();
  });
  document.getElementById('atlas-collapse-all').addEventListener('click', () => {
    data.milestones.forEach(m => atlasMilestoneExpanded.set(m.id, false));
    render();
  });
  document.getElementById('atlas-search').addEventListener('input', render);
  document.getElementById('atlas-status').addEventListener('change', render);
  render();
  if (!atlasRefreshAttempted) refreshAtlasTracker();
}
