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
const external = (href, label, cls = '') => `<a class="${cls}" href="${href}" target="_blank" rel="noopener noreferrer">${label} <span aria-hidden="true">â†—</span></a>`;
const counts = ['validated','progress','planned'].map(state => journal.milestones.filter(item => item.state === state).length);
const fundingTask = journal.tasks.find(task => task.title.startsWith('A03')) || {status:'See work queue', evidence:journal.next};
let activeFilter = 'all';
function sourceLine() {
  return `<div class="source-line"><span class="status-dot"></span><span>Tracker snapshot Â· ${escapeHTML(journal.updated)}</span>${external(sourceURL, 'View source')}<span class="revision">${journal.revision.slice(0,7)}</span></div>`;
}
function milestoneCards() {
  return journal.milestones.map((item, index) => `<article class="milestone ${item.state}"><div class="milestone-top"><span class="milestone-node" aria-hidden="true">${item.state === 'validated' ? 'âœ“' : String(index+1).padStart(2,'0')}</span><span class="pill ${item.state}">${escapeHTML(item.status)}</span></div><span class="milestone-id">${item.id}</span><h3>${escapeHTML(item.title)}</h3><p>${escapeHTML(item.evidence)}</p></article>`).join('');
}
function journeyPanel() {
  return `<section class="panel journey-panel" aria-labelledby="journey-title"><div class="section-heading"><div><p class="eyebrow">THE PATH TO AUTONOMY</p><h2 id="journey-title">Milestone map</h2></div><span class="section-note">Six checkpoints. Evidence at every step.</span></div><div class="milestone-map">${milestoneCards()}</div><p class="map-note">Milestones vary in scope; checkpoint counts are not an overall completion percentage.</p></section>`;
}
function overview() {
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / OPERATING BRIEF</p><h1>Intelligence with discipline.</h1><p class="subtitle">An autonomous trading unit, built around verified evidence and independent controls.</p></div><a class="outline-button" href="#development-journal">Open development journal <span aria-hidden="true">â†—</span></a></div>${sourceLine()}
  <section class="overview-hero"><div><span class="hero-kicker">CURRENT OPERATING MODE</span><h2>Manual, bounded<br>paper trials.</h2><p>${escapeHTML(journal.checkpoint)}</p><span class="dark-pill">Execution disabled</span></div><div class="operating-facts"><div><span>Simulation capital</span><strong>$5,000 <small>USD</small></strong><p>Persistent simulation ledger</p></div><div><span>Annual net return objective</span><strong>15<small>%</small></strong><p>Objective only Â· no measured returns</p></div></div></section>
  <div class="brief-grid"><section class="panel"><p class="eyebrow">DECISION WORKFLOW</p><h2>Independent perspectives.<br>One auditable decision.</h2><div class="role-flow"><span>Research</span><b>â†’</b><span>Portfolio Manager</span><b>â†’</b><span>CEO</span><b>â†’</b><span>Risk & committee</span></div><p class="muted">Six core AI calls, up to nine with research and Portfolio Manager. Proposals operate within binding owner constraints.</p></section><section class="panel next-brief"><p class="eyebrow">NEXT ACCEPTANCE GATE</p><h2>Settlement & funding evidence</h2><p>${escapeHTML(journal.next)}</p><a href="#development-journal" class="inline-link">Explore the work queue â†’</a></section></div>${journeyPanel()}`;
}
function journalView() {
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / ENGINEERING RECORD</p><h1>Development Journal<span class="heading-dot">.</span></h1><p class="subtitle">From first principles to autonomous operations. Every step, backed by evidence.</p></div>${external(sourceURL, 'NexyDAO tracker', 'outline-button')}</div>${sourceLine()}
  <section class="journal-hero"><div class="hero-copy"><span class="hero-kicker">CURRENT CHAPTER / PORTFOLIO & ACCOUNTING</span><h2>Build the foundation.<br>Earn the next milestone.</h2><p>${escapeHTML(journal.checkpoint)}</p><div class="hero-tags"><span>Manual paper trials</span><span>Execution disabled</span></div></div><div class="checkpoint-summary"><div class="checkpoint-row"><strong>${String(counts[0]).padStart(2,'0')}</strong><div><span class="status-dot"></span> Validated<small>Architecture & paper connectivity</small></div></div><div class="checkpoint-row"><strong>${String(counts[1]).padStart(2,'0')}</strong><div><span class="status-dot amber"></span> In progress<small>Research & portfolio accounting</small></div></div><div class="checkpoint-row"><strong>${String(counts[2]).padStart(2,'0')}</strong><div><span class="status-dot gray"></span> Planned<small>Authorization & autonomous operations</small></div></div></div></section>
  ${journeyPanel()}
  <div class="journal-columns"><section class="timeline-section" aria-labelledby="timeline-title"><div class="section-heading"><div><p class="eyebrow">THE DEVELOPMENT RECORD</p><h2 id="timeline-title">Evidence timeline</h2></div><span id="entry-count" class="section-note" role="status"></span></div><div class="timeline-toolbar"><div class="filter-group" role="group" aria-label="Timeline filter"><button data-filter="all" aria-pressed="true">All entries</button><button data-filter="recorded" aria-pressed="false">Recorded work</button><button data-filter="upcoming" aria-pressed="false">Upcoming</button></div><label class="search-label"><span class="sr-only">Search journal</span><input id="journal-search" type="search" placeholder="Search the journalâ€¦"></label></div><p class="timeline-caption">Recorded work includes successful checks, safety stops and open gates. Expand an entry for its evidence.</p><div id="timeline" class="timeline"></div></section>
  <aside class="journal-aside"><section class="panel next-gate"><p class="eyebrow">UP NEXT</p><span class="gate-icon" aria-hidden="true">â†—</span><h2>Close the funding<br>evidence gap.</h2><p>${escapeHTML(journal.next)}</p><div class="gate-status"><span class="status-dot amber"></span> ${escapeHTML(fundingTask.status)}</div><p class="small-note">${escapeHTML(fundingTask.evidence)}</p></section><section class="panel source-card"><p class="eyebrow">SOURCE OF TRUTH</p><h2>NexyDAO</h2><p>Published from the repositoryâ€™s maintained development tracker.</p><dl><dt>Snapshot</dt><dd>${escapeHTML(journal.updated)}</dd><dt>Revision</dt><dd>${journal.revision.slice(0,7)}</dd><dt>Branch</dt><dd>${escapeHTML(journal.branch)}</dd></dl><p class="small-note">A static snapshot of the branch above, refreshed with portal releases.</p>${external(sourceURL, 'Read development tracker', 'inline-link')}${external(`${repoURL}/blob/${journal.revision}/docs/milestones.md`, 'Milestone evidence', 'source-link')}${external(`${repoURL}/blob/${journal.revision}/docs/roadmap.md`, 'Full roadmap', 'source-link')}</section></aside></div>
  <section class="panel queue-panel" aria-labelledby="queue-title"><div class="section-heading"><div><p class="eyebrow">ACCEPTANCE & OPEN GATES</p><h2 id="queue-title">Development work queue</h2></div><span class="section-note">${journal.tasks.length} tracked workstreams</span></div><div class="task-list">${journal.tasks.map(task => `<details class="task"><summary><strong>${escapeHTML(task.title)}</strong><span>${escapeHTML(task.status)}</span></summary><p>${escapeHTML(task.evidence)}</p></details>`).join('')}</div></section>`;
}
function renderTimeline() {
  const query = document.getElementById('journal-search').value.trim().toLowerCase();
  const records = journal.log.map(item => ({...item, upcoming:false})).reverse();
  const upcoming = journal.milestones.filter(item => item.state !== 'validated').map(item => ({date:'Upcoming Â· acceptance gates', title:`${item.id} Â· ${item.title}`, evidence:item.evidence, status:item.status, upcoming:true}));
  let entries = activeFilter === 'upcoming' ? upcoming : activeFilter === 'recorded' ? records : [...upcoming,...records];
  entries = entries.filter(item => `${item.title} ${item.evidence} ${item.date} ${item.status || ''}`.toLowerCase().includes(query));
  let lastDate = '';
  document.getElementById('entry-count').textContent = `${entries.length} entries`;
  document.getElementById('timeline').innerHTML = entries.length ? entries.map(item => {
    const heading = item.date !== lastDate ? `<h3 class="timeline-date">${escapeHTML(item.date)}</h3>` : '';
    lastDate = item.date;
    return `${heading}<details class="timeline-entry ${item.upcoming ? 'upcoming' : ''}"><summary><span class="timeline-marker" aria-hidden="true">${item.upcoming ? 'â—‹' : 'â€¢'}</span><span><span class="entry-label">${item.upcoming ? escapeHTML(item.status) : 'Recorded evidence'}</span><strong>${escapeHTML(item.title)}</strong></span><span class="expand-indicator" aria-hidden="true">+</span></summary><p>${escapeHTML(item.evidence)}</p></details>`;
  }).join('') : '<p class="empty-results" role="status">No entries match your search.</p>';
}
function renderWorkspace() {
  const view = ['#overview','#agentic-architecture','#communication-room','#agent-activity-monitor','#ledger'].includes(location.hash) ? location.hash.slice(1) : 'development-journal';
  document.querySelectorAll('nav a').forEach(link => {
    if (link.hash === '#' + view) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });
  const title = view === 'overview' ? 'Overview' : view === 'agentic-architecture' ? 'Agentic Architecture' : view === 'communication-room' ? 'Communication Room' : view === 'agent-activity-monitor' ? 'Agent Activity Monitor' : view === 'ledger' ? 'Ledger' : 'Development Journal';
  document.title = `Nexy Â· ${title}`;
  document.getElementById('current-view').textContent = title;
  document.getElementById('workspace').classList.toggle('ledger-screen',view === 'ledger');
  document.getElementById('workspace').classList.toggle('monitor-screen',['agent-activity-monitor','ledger'].includes(view));
  document.getElementById('workspace').classList.toggle('ledger-screen',view === 'ledger');
  document.getElementById('workspace').innerHTML = view === 'overview' ? overview() : view === 'agentic-architecture' ? architectureView() : view === 'communication-room' ? communicationView() : view === 'agent-activity-monitor' ? monitorView() : view === 'ledger' ? ledgerView() : journalView();
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
  if (view === 'agentic-architecture') initializeArchitecture();
  if (view === 'communication-room') initializeRoom();
  if (view === 'agent-activity-monitor') initializeMonitor();
  if (view === 'ledger') initializeLedger();
  toggleSidebar(false);
}
const architectureRevision = '7f58bfe20546377558321c6f932feee56fa1c5e6';
const architectureSource = `${repoURL}/blob/${architectureRevision}/docs/architecture.md`;
function roleCard(code, title, description, detail, kind='') {
  return `<details class="org-role ${kind}"><summary><span class="role-code">${code}</span><span><strong>${title}</strong><small>${description}</small></span><span class="role-expand" aria-hidden="true">+</span></summary><p>${detail}</p></details>`;
}
function architectureView() {
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / SYSTEM DOCUMENTATION</p><h1>Agentic Architecture</h1><p class="subtitle">Organization structure, agent responsibilities and the controlled decision workflow.</p></div>${external(architectureSource,'Architecture source','outline-button')}</div>
  <div class="source-line"><span class="status-dot"></span><span>Documentation snapshot · 13 October 2026</span><span class="revision">${architectureRevision.slice(0,7)}</span></div>
  <section class="architecture-summary"><div><p class="eyebrow">CURRENT IMPLEMENTATION</p><h2>Six core roles. Three optional advisory roles.</h2><p>AI agents propose and review decisions. Application code checks evidence, owner policy and capital limits. Broker execution is disabled.</p></div><div class="architecture-numbers"><div><strong>01</strong><span>CEO</span></div><div><strong>02</strong><span>Risk officers</span></div><div><strong>03</strong><span>Committee votes</span></div><div><strong>+03</strong><span>Optional advisors</span></div></div></section>
  <section class="panel organization-panel" aria-labelledby="organization-title"><div class="section-heading"><div><p class="eyebrow">ORGANIZATION & AUTHORITY</p><h2 id="organization-title">Who does what</h2></div><span class="section-note">Expand a role for its authority limits</span></div>
  <div class="org-chart"><div class="org-level owner-level"><span class="org-level-label">OWNER AUTHORITY</span>${roleCard('H','Human owner','Capital · access · binding constraints · intervention','Provides capital, grants or revokes credentials and service access, sets binding constraints above all agents, and can stop operations. Routine strategy and investment proposals belong to the CEO; routine owner approval is not required.','owner-role')}</div>
  <div class="org-connector"><span>Binding policy applies to every role</span></div>
  <div class="org-level ceo-level"><span class="org-level-label">BUSINESS MANAGEMENT</span>${roleCard('01','AI CEO','Mandate · strategy · budget planning · performance oversight','Proposes decisions with rationale, evidence citations, risks and invalidation conditions. Coordinates research and portfolio work within enforced limits. Cannot change capital limits, credentials, spending ceilings or execution locks.','ceo-role')}</div>
  <div class="org-connector"><span>Advisory inputs to CEO review</span></div>
  <div class="org-level"><span class="org-level-label">OPTIONAL ADVISORY INPUTS</span><div class="org-grid three">${roleCard('R1','Opportunity researcher','Candidate ideas from typed filing facts','Receives verified typed observations and bounded memory. Produces an opportunity report with source-bound numeric claims. Cannot retrieve arbitrary sources or use network tools; prose and forecasts remain unverified.')}${roleCard('R2','Countercase researcher','Independent challenges to candidate theses','Receives the same facts without the opportunity report. Produces risks and counterarguments in a separate call. Numeric claims are checked by application code; the report cannot authorize investments.')}${roleCard('PM','Portfolio Manager','Allocation proposals · alternatives · portfolio risks','Adds an advisory allocation plan before CEO review. Independent code checks quote bindings, funding and exposure. Has no ledger or broker mutation tools. Live quote-free abstention validated; positive allocations tested offline.')}</div></div>
  <div class="org-connector"><span>CEO proposal → independent risk review</span></div>
  <div class="org-level"><span class="org-level-label">INDEPENDENT RISK REVIEW</span><div class="org-grid two">${roleCard('02','Capital Risk Officer','Loss · position sizing · liquidity','Receives the proposal in a fresh call without the other officer’s response. Passes, challenges or vetoes. The CEO cannot overrule a risk veto.','review-role')}${roleCard('03','Evidence Risk Officer','Provenance · evidence quality · security','Independently examines evidence and security concerns without the capital officer’s response. Both risk officers must pass the policy gate.','review-role')}</div></div>
  <div class="org-connector"><span>Proposal + both reviews → committee</span></div>
  <div class="org-level"><span class="org-level-label">ADVISORY COMMITTEE</span><div class="org-grid three">${roleCard('04','Investment member','Investment review vote','Independently votes approve, revise or reject using the proposal and both risk reviews. Does not see the other committee votes.','review-role')}${roleCard('05','Fiduciary member','Fiduciary review vote','Reviews the proposal through the fiduciary role prompt and votes independently. Two of three approvals are required, together with both risk passes.','review-role')}${roleCard('06','Audit member','Audit review vote','Reviews the proposal through the audit role prompt and casts an independent vote. This agent is distinct from the persistent audit store and planned external auditor.','review-role')}</div></div></div>
  <p class="architecture-note">The diagram shows authority and information flow. Calls are sequential. Separate prompts do not establish statistical independence; calls to the same model can share errors and biases.</p></section>
  <section class="panel workflow-panel" aria-labelledby="workflow-title"><div class="section-heading"><div><p class="eyebrow">INPUTS → PROPOSAL → REVIEW → RECORD</p><h2 id="workflow-title">Decision-making flow</h2></div><span id="workflow-count" class="workflow-count" role="status"></span></div><div class="workflow-options" role="group" aria-label="Workflow configuration"><button data-workflow="core" aria-pressed="true">Core review</button><button data-workflow="research" aria-pressed="false">With research</button><button data-workflow="portfolio" aria-pressed="false">With portfolio</button><button data-workflow="both" aria-pressed="false">Research + portfolio</button></div><ol id="decision-flow" class="decision-flow"></ol><div class="failure-path"><span aria-hidden="true">↳</span><div><strong>Failure or incomplete output → stop and record</strong><p>Partial decisions never become authorized. No automatic resubmission loop. Future proposal revisions require new linked proposals and all reviews again. Hold or request research are valid outcomes.</p></div></div></section>
  <div class="architecture-bottom"><section class="panel"><p class="eyebrow">INDEPENDENT APPLICATION CHECKS</p><h2>Decision gates</h2><div class="gate-equation"><span>Both risk passes</span><b>+</b><span>2 / 3 approvals</span><b>+</b><span>Policy & capital checks</span></div><div class="execution-denied"><span aria-hidden="true">⊘</span><div><strong>Execution denied</strong><p>Passing reviews does not grant broker authority. Current execution denial applies to every proposal, including unanimous approval.</p></div></div><ul class="architecture-rules"><li>Owner constraints supersede agent proposals and votes.</li><li>No shorts, leverage or borrowing; independently verified funding is required.</li><li>Future live execution requires independent legal and Swedish ISK eligibility checks.</li></ul></section>
  <section class="panel"><p class="eyebrow">SYSTEM BOUNDARIES</p><h2>Agents receive data, not tools</h2><div class="boundary-stack"><div><span>01</span><p><strong>Read-only collectors & controller</strong>Collect bounded paper quotes and SEC facts; verify signatures, identity and freshness. Manual inputs are labelled unverified.</p></div><div><span>02</span><p><strong>Model reasoning layer</strong>Serialized inputs only. No shell, filesystem, database, credentials or broker tools. Typed numeric claims are checked; prose and forecasts are unverified.</p></div><div><span>03</span><p><strong>Policy, accounting & SQLite records</strong>Independent constraints, budget reservations, usage/cost estimates, role outputs and bounded memory. Durable local history is not tamper-proof against an OS administrator.</p></div></div></section></div>
  <section class="panel architecture-future"><div><p class="eyebrow">PLANNED / M4–M5</p><h2>Execution and operational components</h2></div><div class="org-grid three"><article><span class="pill planned">Planned</span><h3>Isolated executor</h3><p>Separate OS identity, short-lived signed permits, kill switch, exposure reservations and replay/idempotency checks before paper orders.</p></article><article><span class="pill planned">Planned</span><h3>Independent external audit</h3><p>Tamper-evident external records and outcome review beyond the current local SQLite history.</p></article><article><span class="pill planned">Planned</span><h3>Autonomous paper operations</h3><p>Bounded scheduling, recovery, alerts, outcome learning and sustained evaluation. Current trials are manual.</p></article></div></section>
  <div class="architecture-sources">${external(architectureSource,'Architecture & workflow')}${external(`${repoURL}/blob/${architectureRevision}/docs/owner-policy.md`,'Owner policy')}${external(`${repoURL}/blob/${architectureRevision}/docs/research.md`,'Research boundaries')}${external(`${repoURL}/blob/${architectureRevision}/docs/portfolio.md`,'Portfolio Manager')}</div>`;
}
function renderDecisionFlow(mode) {
  const research = mode === 'research' || mode === 'both';
  const portfolio = mode === 'portfolio' || mode === 'both';
  const steps = [{title:'Verify inputs',kind:'Application',text:'Controller checks receipt identity, integrity and freshness; loads three recent completed records and internally reconciled simulation state.'}];
  if (research) steps.push({title:'Research reports',kind:'2 AI calls',text:'Opportunity and countercase researchers receive separate contexts. Application code verifies structured numeric claim bindings before CEO review.'});
  if (portfolio) steps.push({title:'Portfolio plan',kind:'1 AI call',text:'Portfolio Manager proposes allocations and alternatives; application code independently checks quotes, funding and aggregate exposure.'});
  steps.push({title:'CEO proposal',kind:'1 AI call',text:'Decision, rationale, citations, risks and invalidation conditions.'},{title:'Risk reviews',kind:'2 AI calls',text:'Capital and evidence officers each pass, challenge or veto. Separate calls; neither sees the other’s response.'},{title:'Committee votes',kind:'3 AI calls',text:'Investment, fiduciary and audit members approve, revise or reject. Each sees both risk reviews, not the other votes.'},{title:'Policy gate',kind:'Application',text:'Checks both risk passes, committee quorum, owner constraints, evidence and capital. Execution remains denied.'},{title:'Persist result',kind:'Application',text:'SQLite records inputs, each role, final status, versions, model, usage and estimated cost. Incomplete runs are excluded from memory.'});
  document.getElementById('workflow-count').textContent = `${6 + (research ? 2 : 0) + (portfolio ? 1 : 0)} sequential AI calls`;
  document.getElementById('decision-flow').innerHTML = steps.map((step,index)=>`<li><span class="flow-number">${String(index+1).padStart(2,'0')}</span><span class="flow-kind">${step.kind}</span><h3>${step.title}</h3><p>${step.text}</p></li>`).join('');
}
function initializeArchitecture() {
  renderDecisionFlow('core');
  document.querySelectorAll('[data-workflow]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-workflow]').forEach(option=>option.setAttribute('aria-pressed',String(option===button)));
    renderDecisionFlow(button.dataset.workflow);
  }));
}
window.addEventListener('hashchange', () => { renderWorkspace(); window.scrollTo(0,0); });
renderWorkspace();
