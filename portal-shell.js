"use strict";
function toggleSidebar(force) {
  const sidebar = document.getElementById('sidebar');
  const open = typeof force === 'boolean' ? force : !sidebar.classList.contains('open');
  sidebar.classList.toggle('open', open);
  document.getElementById('sidebar-backdrop').classList.toggle('hidden', !open);
  document.getElementById('menu-button').setAttribute('aria-expanded', String(open));
}
document.addEventListener('keydown', event => { if (event.key === 'Escape') toggleSidebar(false); });
const journal = window.NEXY_JOURNAL;
const escapeHTML = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const repoURL = 'https://github.com/mithunkurian/NexyDAO';
const sourceURL = `${repoURL}/blob/${journal.revision}/docs/development-tracker.md`;
const external = (href, label, cls = '') => `<a class="${cls}" href="${href}" target="_blank" rel="noopener noreferrer">${label} <span aria-hidden="true">↗</span></a>`;
const counts = ['validated','progress','planned'].map(state => journal.milestones.filter(item => item.state === state).length);
const fundingTask = journal.tasks.find(task => task.title.startsWith('A03')) || {status:'See work queue', evidence:journal.next};
let activeFilter = 'all';
function sourceLine() {
  return `<div class="source-line"><span class="status-dot"></span><span>Tracker snapshot · ${escapeHTML(journal.updated)}</span>${external(sourceURL, 'View source')}<span class="revision">${journal.revision.slice(0,7)}</span></div>`;
}
function milestoneCards() {
  return journal.milestones.map((item, index) => `<article class="milestone ${item.state}"><div class="milestone-top"><span class="milestone-node" aria-hidden="true">${item.state === 'validated' ? '✓' : String(index+1).padStart(2,'0')}</span><span class="pill ${item.state}">${escapeHTML(item.status)}</span></div><span class="milestone-id">${item.id}</span><h3>${escapeHTML(item.title)}</h3><p>${escapeHTML(item.evidence)}</p></article>`).join('');
}
function journeyPanel() {
  return `<section class="panel journey-panel" aria-labelledby="journey-title"><div class="section-heading"><div><p class="eyebrow">THE PATH TO AUTONOMY</p><h2 id="journey-title">Milestone map</h2></div><span class="section-note">Six checkpoints. Evidence at every step.</span></div><div class="milestone-map">${milestoneCards()}</div><p class="map-note">Milestones vary in scope; checkpoint counts are not an overall completion percentage.</p></section>`;
}
function overview() {
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / OPERATING BRIEF</p><h1>Intelligence with discipline.</h1><p class="subtitle">An autonomous trading unit, built around verified evidence and independent controls.</p></div><a class="outline-button" href="#development-journal">Open development journal <span aria-hidden="true">↗</span></a></div>${sourceLine()}
  <section class="overview-hero"><div><span class="hero-kicker">CURRENT OPERATING MODE</span><h2>Manual, bounded<br>paper trials.</h2><p>${escapeHTML(journal.checkpoint)}</p><span class="dark-pill">Execution disabled</span></div><div class="operating-facts"><div><span>Simulation capital</span><strong>$5,000 <small>USD</small></strong><p>Persistent simulation ledger</p></div><div><span>Annual net return objective</span><strong>15<small>%</small></strong><p>Objective only · no measured returns</p></div></div></section>
  <div class="brief-grid"><section class="panel"><p class="eyebrow">DECISION WORKFLOW</p><h2>Independent perspectives.<br>One auditable decision.</h2><div class="role-flow"><span>Research</span><b>→</b><span>Portfolio Manager</span><b>→</b><span>CEO</span><b>→</b><span>Risk & committee</span></div><p class="muted">Six core AI calls, up to nine with research and Portfolio Manager. Proposals operate within binding owner constraints.</p></section><section class="panel next-brief"><p class="eyebrow">NEXT ACCEPTANCE GATE</p><h2>Settlement & funding evidence</h2><p>${escapeHTML(journal.next)}</p><a href="#development-journal" class="inline-link">Explore the work queue →</a></section></div>${journeyPanel()}`;
}
function journalView() {
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / ENGINEERING RECORD</p><h1>Development Journal<span class="heading-dot">.</span></h1><p class="subtitle">From first principles to autonomous operations. Every step, backed by evidence.</p></div>${external(sourceURL, 'NexyDAO tracker', 'outline-button')}</div>${sourceLine()}
  <section class="journal-hero"><div class="hero-copy"><span class="hero-kicker">CURRENT CHAPTER / PORTFOLIO & ACCOUNTING</span><h2>Build the foundation.<br>Earn the next milestone.</h2><p>${escapeHTML(journal.checkpoint)}</p><div class="hero-tags"><span>Manual paper trials</span><span>Execution disabled</span></div></div><div class="checkpoint-summary"><div class="checkpoint-row"><strong>${String(counts[0]).padStart(2,'0')}</strong><div><span class="status-dot"></span> Validated<small>Architecture & paper connectivity</small></div></div><div class="checkpoint-row"><strong>${String(counts[1]).padStart(2,'0')}</strong><div><span class="status-dot amber"></span> In progress<small>Research & portfolio accounting</small></div></div><div class="checkpoint-row"><strong>${String(counts[2]).padStart(2,'0')}</strong><div><span class="status-dot gray"></span> Planned<small>Authorization & autonomous operations</small></div></div></div></section>
  ${journeyPanel()}
  <div class="journal-columns"><section class="timeline-section" aria-labelledby="timeline-title"><div class="section-heading"><div><p class="eyebrow">THE DEVELOPMENT RECORD</p><h2 id="timeline-title">Evidence timeline</h2></div><span id="entry-count" class="section-note" role="status"></span></div><div class="timeline-toolbar"><div class="filter-group" role="group" aria-label="Timeline filter"><button data-filter="all" aria-pressed="true">All entries</button><button data-filter="recorded" aria-pressed="false">Recorded work</button><button data-filter="upcoming" aria-pressed="false">Upcoming</button></div><label class="search-label"><span class="sr-only">Search journal</span><input id="journal-search" type="search" placeholder="Search the journal…"></label></div><p class="timeline-caption">Recorded work includes successful checks, safety stops and open gates. Expand an entry for its evidence.</p><div id="timeline" class="timeline"></div></section>
  <aside class="journal-aside"><section class="panel next-gate"><p class="eyebrow">UP NEXT</p><span class="gate-icon" aria-hidden="true">↗</span><h2>Close the funding<br>evidence gap.</h2><p>${escapeHTML(journal.next)}</p><div class="gate-status"><span class="status-dot amber"></span> ${escapeHTML(fundingTask.status)}</div><p class="small-note">${escapeHTML(fundingTask.evidence)}</p></section><section class="panel source-card"><p class="eyebrow">SOURCE OF TRUTH</p><h2>NexyDAO</h2><p>Published from the repository’s maintained development tracker.</p><dl><dt>Snapshot</dt><dd>${escapeHTML(journal.updated)}</dd><dt>Revision</dt><dd>${journal.revision.slice(0,7)}</dd><dt>Branch</dt><dd>${escapeHTML(journal.branch)}</dd></dl><p class="small-note">A static snapshot of the branch above, refreshed with portal releases.</p>${external(sourceURL, 'Read development tracker', 'inline-link')}${external(`${repoURL}/blob/${journal.revision}/docs/milestones.md`, 'Milestone evidence', 'source-link')}${external(`${repoURL}/blob/${journal.revision}/docs/roadmap.md`, 'Full roadmap', 'source-link')}</section></aside></div>
  <section class="panel queue-panel" aria-labelledby="queue-title"><div class="section-heading"><div><p class="eyebrow">ACCEPTANCE & OPEN GATES</p><h2 id="queue-title">Development work queue</h2></div><span class="section-note">${journal.tasks.length} tracked workstreams</span></div><div class="task-list">${journal.tasks.map(task => `<details class="task"><summary><strong>${escapeHTML(task.title)}</strong><span>${escapeHTML(task.status)}</span></summary><p>${escapeHTML(task.evidence)}</p></details>`).join('')}</div></section>`;
}
function renderTimeline() {
  const query = document.getElementById('journal-search').value.trim().toLowerCase();
  const records = journal.log.map(item => ({...item, upcoming:false})).reverse();
  const upcoming = journal.milestones.filter(item => item.state !== 'validated').map(item => ({date:'Upcoming · acceptance gates', title:`${item.id} · ${item.title}`, evidence:item.evidence, status:item.status, upcoming:true}));
  let entries = activeFilter === 'upcoming' ? upcoming : activeFilter === 'recorded' ? records : [...upcoming,...records];
  entries = entries.filter(item => `${item.title} ${item.evidence} ${item.date} ${item.status || ''}`.toLowerCase().includes(query));
  let lastDate = '';
  document.getElementById('entry-count').textContent = `${entries.length} entries`;
  document.getElementById('timeline').innerHTML = entries.length ? entries.map(item => {
    const heading = item.date !== lastDate ? `<h3 class="timeline-date">${escapeHTML(item.date)}</h3>` : '';
    lastDate = item.date;
    return `${heading}<details class="timeline-entry ${item.upcoming ? 'upcoming' : ''}"><summary><span class="timeline-marker" aria-hidden="true">${item.upcoming ? '○' : '•'}</span><span><span class="entry-label">${item.upcoming ? escapeHTML(item.status) : 'Recorded evidence'}</span><strong>${escapeHTML(item.title)}</strong></span><span class="expand-indicator" aria-hidden="true">+</span></summary><p>${escapeHTML(item.evidence)}</p></details>`;
  }).join('') : '<p class="empty-results" role="status">No entries match your search.</p>';
}
function renderWorkspace() {
  const view = location.hash === '#overview' ? 'overview' : 'development-journal';
  document.querySelectorAll('nav a').forEach(link => {
    if (link.hash === '#' + view) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });
  const title = view === 'overview' ? 'Overview' : 'Development Journal';
  document.title = `Nexy · ${title}`;
  document.getElementById('current-view').textContent = title;
  document.getElementById('workspace').innerHTML = view === 'overview' ? overview() : journalView();
  if (view === 'development-journal') {
    activeFilter = 'all';
    renderTimeline();
    document.getElementById('journal-search').addEventListener('input', renderTimeline);
    document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach(filter => filter.setAttribute('aria-pressed', String(filter === button)));
      renderTimeline();
    }));
  }
  toggleSidebar(false);
}
window.addEventListener('hashchange', () => { renderWorkspace(); window.scrollTo(0,0); });
renderWorkspace();
