"use strict";
// Private, read-only data fetched after verified Google authentication. Never persisted.
window.AtlasLive = (() => {
  const endpoint = 'https://firestore.googleapis.com/v1/projects/portalnexy/databases/(default)/documents/atlas_operator_live_v1/current';
  let user = null, data = null, generation = 0, active = false, timer = null, ticker = null, controller = null;
  let state = 'Sign in to view private paper telemetry.';
  const esc = v => String(v ?? 'Unknown').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v)) ? new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'}).format(Number(v)) : 'Unknown';
  const age = stamp => { const n = Date.parse(stamp); return Number.isFinite(n) ? (Date.now()-n)/1000 : Infinity; };
  const table = (headers, rows) => `<div class="atlas-table-wrap"><table class="atlas-live-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length ? rows.map(row=>`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${headers.length}">No recorded entries.</td></tr>`}</tbody></table></div>`;
  let modal = null, returnFocus = null, revision = 0, renderedRevision = -1, renderedFreshness = null;
  const names = {scheduled:'Scheduled',readiness:'Readiness checks',screening:'Market screening',analysis:'News & AI analysis',risk:'Risk checks',orders:'Orders & active trades',reconciliation:'Reconciliation',completed:'Completed'};
  const statuses = new Set(['upcoming','running','completed','skipped','blocked','unknown']);
  const ordinal = n => `${n}${n%100>=11&&n%100<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th')}`;
  function stamp(value, zone='Europe/Stockholm') {
    const date = new Date(value || ''); if(!Number.isFinite(date.getTime())) return 'Not recorded';
    const parts = new Intl.DateTimeFormat('en-GB',{timeZone:zone,day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit',hour12:true}).formatToParts(date);
    const part = type => parts.find(p=>p.type===type)?.value || '';
    return `${ordinal(Number(part('day')))} ${part('month')}. ${part('year')} · ${part('hour')}:${part('minute')} ${part('dayPeriod').toUpperCase()}`;
  }
  const statusName = status => ({upcoming:'Upcoming',running:'Running',completed:'Completed',skipped:'Skipped',blocked:'Blocked',unknown:'Unknown'}[status] || 'Unknown');
  function stages() {
    return Object.entries(names).map(([id,label])=>{
      const row = data?.daily?.stages?.find(r=>r.id===id);
      const status = statuses.has(row?.status) ? row.status : 'unknown';
      return {...row,id,label,status:age(data?.published_at)>30&&status==='running'?'unknown':status,
        detail:row?.detail || 'Detailed stage evidence is not available yet.'};
    });
  }
  function view() { return `<section class="page-intro"><p class="eyebrow">ATLAS / PRIVATE PAPER MONITOR</p><h1>ATLAS Dashboard</h1><p>NASDAQ · USD · paper trading</p></section><div id="atlas-live-content"></div><dialog id="atlas-live-dialog" class="atlas-dialog" aria-labelledby="atlas-dialog-title"><header><div><p class="eyebrow">ATLAS / DETAILS</p><h2 id="atlas-dialog-title">Details</h2></div><button type="button" class="atlas-dialog-close" aria-label="Close details">×</button></header><div id="atlas-dialog-body"></div></dialog>`; }
  function freshness() {
    const relay = age(data?.published_at)>=-2&&age(data?.published_at)<=30;
    return {relay,source:relay&&data?.source_valid===true&&age(data?.source_at)>=-2&&age(data?.source_at)<=15};
  }
  function remaining() {
    const daily=data?.daily, delay=Date.parse(daily?.scheduled_at)-Date.now();
    if(!daily) return 'Detailed daily activity is not available yet.';
    if(data.schedule?.rescan_minutes===15) {
      if(data.schedule.enabled!==true)return 'Intraday scans are disabled; owned position supervision is separate.';
      if(!freshness().relay||!freshness().source)return 'Broker data status is unconfirmed; fresh readiness is required before another scan.';
      if(daily.job_status==='running')return 'A scan is in progress; owned commitments take priority over another scan.';
      if(data.position_health?.active_intents>0)return 'Owned commitments are being supervised; new scans wait until flat.';
      if(!freshness().source||data.risk_stopped===true||data.execution_enabled!==true)return 'Entries paused: another scan requires fresh independent readiness and a guarded resume.';
      const next=Date.parse(daily.next_scan_at);
      if(!Number.isFinite(next))return 'The intraday scan window has ended; position supervision continues.';
      const minutes=Math.max(0,Math.ceil((next-Date.now())/60000));
      return `Next planned scan in ${minutes}m · every 15 minutes before 1 PM New York, only when flat and ready`;
    }
    if(daily.job_status) return daily.stages?.find(r=>r.id==='completed')?.status==='completed'?'Daily activity finished.':'Time remaining: not yet known.';
    if(data.schedule?.enabled!==true) return 'Daily schedule is disabled.';
    if(!Number.isFinite(delay)) return 'Next scheduled time is not confirmed.';
    if(delay<=-60000) return 'The configured window ended without a recorded job; no catch-up.';
    if(delay<=0) return 'The configured window has arrived; execution requires fresh readiness.';
    const minutes=Math.ceil(delay/60000), hours=Math.floor(minutes/60);
    return `Configured start in ${hours?`${hours}h `:''}${minutes%60}m · session eligibility checked at runtime`;
  }
  function healthText() {
    const health=data?.position_health;
    if(!health)return 'Position health review: not recorded.';
    if(!freshness().relay||!freshness().source)return 'Position health unconfirmed: fresh broker data is required; broker protection remains independent.';
    if(health.state==='no_open_positions')return 'Owned journal: no open commitments to review.';
    const reviewAge=Date.now()-Date.parse(health.last_review?.observed_at);
    if(!Number.isFinite(reviewAge)||reviewAge>60000||reviewAge<0)return 'Position health unconfirmed: no fresh minute-level review is available.';
    if(health.state==='hold')return 'Hold: fresh broker state and protection verified; health is reviewed at least every minute.';
    if(health.state==='exit')return 'Exit or owned recovery was triggered; terminal flat confirmation is still required.';
    return 'Position health unconfirmed: broker checks must verify protection and decide hold or recovery.';
  }
  function metroMap(timeline) {
    const recurring=data.schedule?.rescan_minutes===15;
    const health=data.position_health,reviewAge=Date.now()-Date.parse(health?.last_review?.observed_at);
    const verified=freshness().source&&Number.isFinite(reviewAge)&&reviewAge>=0&&reviewAge<=60000;
    const review=health?.state==='no_open_positions'&&freshness().source?'idle':verified&&['hold','exit'].includes(health?.state)?health.state:'unconfirmed';
    const positions={scheduled:60,readiness:180,screening:300,analysis:420,risk:540,orders:660,reconciliation:900,completed:1020};
    const labels={scheduled:'Scheduled',readiness:'Readiness',screening:'Screening',analysis:'News & AI',risk:'Risk checks',orders:'Entry / position',reconciliation:'Reconciliation',completed:'Attempt resolved'};
    const station=(r,i)=>`<li class="atlas-map-stop atlas-stage ${r.status}" style="left:${positions[r.id]/11.2}%;top:46.1538%"><button data-detail="stage:${r.id}" aria-label="${esc(r.label)}: ${statusName(r.status)}"><span class="atlas-stage-node" aria-hidden="true">${r.status==='completed'?'✓':r.status==='skipped'?'−':i+1}</span><span class="atlas-stage-name">${labels[r.id]}</span><span class="atlas-stage-status">${statusName(r.status)}</span></button></li>`;
    const loopStop=(x,y,key,label,note,route)=>`<li class="atlas-map-stop atlas-map-loop-stop ${route}" style="left:${x/11.2}%;top:${y/5.2}%"><button data-detail="loop:${key}"><span class="atlas-stage-node" aria-hidden="true">↶</span><span class="atlas-stage-name">${label}</span><span class="atlas-stage-status">${note}</span></button></li>`;
    return `<div class="atlas-daily-metro" aria-label="Daily schedule with opportunity and position-health loops">
      <div class="atlas-map-key"><span><i class="main"></i>Main flow <b>→</b></span><span id="atlas-scan-loop-title"><i class="scan"></i>Opportunity scan loop · ${recurring?'every 15 min':'intraday off'}</span><span id="atlas-health-loop-title"><i class="health"></i>Position health loop · every minute</span></div>
      <p class="atlas-map-pan">Swipe or scroll across the map to follow the route. Select any station for details.</p>
      <div class="atlas-map-scroll" tabindex="0" role="region" aria-label="Daily route map; scroll horizontally on smaller screens">
      <div class="atlas-route-board">
        <svg class="atlas-route-lines" viewBox="0 0 1120 520" aria-hidden="true">
          <defs><marker id="atlas-arrow-main" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#20677d"/></marker><marker id="atlas-arrow-scan" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#b85ba8"/></marker><marker id="atlas-arrow-health" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#27805e"/></marker></defs>
          <path class="atlas-rail scan" d="M540 240 V105 Q540 80 515 80 H205 Q180 80 180 105 V240"/>
          <path class="atlas-rail health" d="M780 240 V375 Q780 400 805 400 H925 Q950 400 950 375 V350 Q950 325 925 325 H805 Q780 325 780 300 V240"/>
          <path class="atlas-rail main" d="M60 240 H1020"/>
          <path class="atlas-direction scan" d="M380 80 H350" marker-end="url(#atlas-arrow-scan)"/><path class="atlas-direction scan" d="M180 180 V208" marker-end="url(#atlas-arrow-scan)"/>
          <path class="atlas-direction main" d="M225 240 H250 M585 240 H610 M820 240 H850 M945 240 H970" marker-end="url(#atlas-arrow-main)"/>
          <path class="atlas-direction health" d="M830 400 H855" marker-end="url(#atlas-arrow-health)"/><path class="atlas-direction health" d="M860 325 H830" marker-end="url(#atlas-arrow-health)"/>
        </svg>
        <span class="atlas-route-caption scan" style="left:31%;top:2%">NO ENTRY → NEXT ELIGIBLE SLOT</span>
        <span class="atlas-route-caption scan atlas-map-condition" style="left:48.2%;top:30%">No eligible entry</span>
        <span class="atlas-route-caption atlas-map-condition" style="left:54%;top:35%">Accepted entry →</span>
        <span class="atlas-route-caption atlas-map-condition" style="left:75%;top:35%">Exit / resolution →</span>
        <span class="atlas-route-caption health" style="left:78%;top:94%">HOLD → REVIEW AGAIN</span>
        <ol class="atlas-route-stations" aria-label="Recorded attempt stations and current position review">${timeline.map(station).join('')}
          <li class="atlas-map-stop atlas-health-stop ${review}" style="left:69.6429%;top:46.1538%"><button data-detail="loop:health" aria-label="Minute-level hold or exit review"><span class="atlas-stage-node" aria-hidden="true">↻</span><span class="atlas-stage-name">Health review</span><span class="atlas-stage-status">${{idle:'No open position',hold:'Hold',exit:'Exit trigger',unconfirmed:'Unconfirmed'}[review]}</span></button></li>
          ${loopStop(420,80,'scan',recurring?'Next 15-min slot':'Next daily slot',recurring?'Last start 12:45 NY':'Intraday disabled','scan')}
          ${loopStop(270,80,'flat','Flat & ready','Fresh checks each time','scan')}
          ${loopStop(900,400,'hold','Hold / wait','Review within a minute','health')}
        </ol>
      </div></div>
      <div class="atlas-map-notes"><p id="atlas-start-countdown" class="scan">${esc(remaining())}</p><p data-position-health class="health">${esc(healthText())}</p></div>
      <p class="atlas-metro-note">No eligible entry at screening, analysis or risk returns to the next slot and fresh readiness. Hold returns to health review; an exit proceeds to reconciliation. Once flat, another scan still needs its open window. New scans stop before 1 PM New York; position monitoring continues.</p>
      <p class="atlas-metro-note">Route colors explain the flow. Station colors show recorded attempt status; unavailable broker data never means Hold.</p>
    </div>`;
  }
  function render() {
    const target = document.getElementById('atlas-live-content');
    if (!target) return;
    if (!data) { target.innerHTML = `<section class="panel"><h2>Private connection</h2><p role="status">${esc(state)}</p></section>`; return; }
    const fresh=freshness(), freshKey=`${fresh.relay}:${fresh.source}`;
    if(renderedRevision===revision&&renderedFreshness===freshKey){const countdown=document.getElementById('atlas-start-countdown');if(countdown)countdown.textContent=remaining();return;}
    const focused=document.activeElement?.closest('[data-detail]')?.dataset.detail;
    renderedRevision=revision;renderedFreshness=freshKey;
    const history=data.history||{},perf=history.performance||{},money=fresh.source?data.money||{}:{};
    const timeline=stages(),resolved=timeline.filter(r=>['completed','skipped'].includes(r.status)).length;
    const headline=!fresh.relay?'Live updates unavailable':!fresh.source?'Broker status unconfirmed':data.daily?.summary||'Connected to ATLAS';
    const connection=!fresh.relay?'Current status cannot be confirmed. Last recorded activity is shown.':!fresh.source?'Current financial values unknown. Fresh broker data is required.':data.execution_enabled?'Independent paper entries are enabled.':'Paper entries are paused.';
    const metric=(name,value,note)=>`<article class="panel atlas-metric"><span>${esc(name)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
    const detailButton=(id,label,note)=>`<button type="button" class="atlas-detail-button" data-detail="${id}"><span>${esc(label)}</span><small>${esc(note)}</small><b aria-hidden="true">↗</b></button>`;
    target.innerHTML=`<section class="panel atlas-connection"><div><p class="eyebrow">TODAY / PAPER TRADING</p><h2 aria-live="polite">${esc(headline)}</h2><p>${esc(connection)}</p><p class="atlas-time">Last broker update: ${esc(stamp(data.source_at))} · Stockholm time</p></div><span class="pill">Read-only</span></section>
      <div class="atlas-metrics">${metric('Allocated capital',usd(money.strategy_capital_usd),'Verified current allocation')}${metric('Owned daily P&L',usd(money.owned_day_pnl_usd),'Market day · New York')}${metric('Open exposure',usd(money.owned_exposure_usd),'ATLAS-owned positions')}${metric('Open risk',usd(money.owned_open_risk_usd),'Independent current policy')}</div>
      <section class="panel atlas-daily" aria-labelledby="atlas-daily-title"><div class="atlas-daily-heading"><div><p class="eyebrow">DAILY ACTIVITY</p><h2 id="atlas-daily-title">Today's progress</h2><p>${esc(data.daily?.summary||'Waiting for detailed stage evidence')}</p></div><span class="atlas-resolved">${resolved} of ${timeline.length} stages resolved</span></div>
      <p class="atlas-time">Attempt start: ${esc(stamp(data.daily?.scheduled_at))} Stockholm · ${esc(stamp(data.daily?.scheduled_at,'America/New_York'))} New York</p>
      ${metroMap(timeline)}
      <div class="atlas-stage-legend" aria-label="Stage status legend">${['completed','running','upcoming','skipped','blocked','unknown'].map(s=>`<span class="${s}"><i aria-hidden="true"></i>${statusName(s)}</span>`).join('')}</div><p class="atlas-time">Select a stage for its recorded times, results and next requirement. A no-trade decision can complete the day without placing an order.</p></section>
      <section class="panel atlas-performance-summary"><div><p class="eyebrow">STRATEGY PERFORMANCE</p><h2>${esc(perf.closed_trades??'Unknown')} closed strategy trades</h2><p>Net ${esc(perf.verified===true&&perf.closed_trades>0?usd(perf.net_profit_usd):'not yet available')} · Commissioning checks are reported separately.</p></div><button type="button" class="atlas-secondary-button" data-detail="performance">Performance details</button></section>
      <section class="panel atlas-detail-section" aria-labelledby="atlas-details-title"><p class="eyebrow">EXPLORE THE RECORD</p><h2 id="atlas-details-title">Details when you need them</h2><div class="atlas-detail-grid">${detailButton('positions','Positions','Owned quantities and trade intentions')}${detailButton('history','Trade history',`${history.total_fills??'Unknown'} recorded owned fills`)}${detailButton('activity','Activity','Daily jobs and operational events')}${detailButton('decisions','Decisions','Why today did or did not trade')}${detailButton('settings','Settings','Read-only limits, schedule and connection')}</div></section>`;
    if(focused&&!modal) target.querySelector(`[data-detail="${focused}"]`)?.focus({preventScroll:true});
    if(modal)renderModal();
  }
  function detailContent(key) {
    const history=data.history||{},limits=data.limits||{},configured=limits.configured_limits||{},perf=history.performance||{};
    if(key==='loop:scan'||key==='loop:flat')return {title:'How the scan loop repeats',body:`<p>${esc(remaining())}</p><p>When intraday scans are enabled, fresh opportunities start every 15 minutes from 10:15 through 12:45 New York, while flat and independently ready. No new scan starts at 1 PM.</p><p>No eligible entry returns to the next planned slot. An owned commitment transfers priority to position supervision. Missed or failed slots never replay; source recovery does not automatically resume entries.</p>`};
    if(key==='loop:health'||key==='loop:hold')return {title:'Minute-level position supervision',body:`<p>${esc(healthText())}</p><p>Native broker protection, daily-loss limits and exit deadlines determine Hold or owned exit/recovery. A Hold needs fresh verified evidence; unavailable data or an overdue review is Unconfirmed.</p><p>Hold returns to another review within a minute while sources are healthy. An exit trigger leads to reconciliation; it does not prove the position is closed. Monitoring continues after 1 PM. Once flat and reconciled, a later scan still needs its own open window and fresh readiness.</p>`};
    if(key.startsWith('stage:')) {
      const row=stages().find(r=>r.id===key.slice(6));if(!row)return null;
      const failure=data.daily?.failure?.stage===row.id?data.daily.failure:null;
      const failureInfo=failure?`<h3>Recorded failure</h3><dl class="atlas-detail-list"><dt>Category</dt><dd>${esc(failure.kind.replaceAll('_',' '))}</dd><dt>Source boundary</dt><dd>${esc((failure.boundary||'Not recorded').replaceAll('_',' '))}</dd><dt>API diagnostic codes</dt><dd>${esc(Array.isArray(failure.api_codes)&&failure.api_codes.length?failure.api_codes.join(', '):'Not recorded')}</dd><dt>Recorded</dt><dd>${esc(stamp(failure.recorded_at))}</dd></dl>`:'';
      return {title:row.label,body:`<p class="atlas-stage-detail-status ${row.status}">${statusName(row.status)}</p><p>${esc(row.detail)}</p><dl class="atlas-detail-list"><dt>Scheduled</dt><dd>${row.scheduled_at?esc(stamp(row.scheduled_at)):'Not separately scheduled'}</dd><dt>Started</dt><dd>${esc(stamp(row.started_at))}</dd><dt>Finished</dt><dd>${esc(stamp(row.finished_at))}</dd><dt>Recorded count</dt><dd>${esc(row.count??'Not recorded')}</dd><dt>Time remaining</dt><dd>${row.id==='scheduled'&&row.status==='upcoming'?esc(remaining()):'Not yet known; no execution duration is assumed.'}</dd></dl>${failureInfo}<p class="atlas-time">All times shown in Stockholm. ${!freshness().relay?'Live updates are unavailable; these are last recorded events.':'Only recorded execution evidence marks a stage complete.'}</p>`};
    }
    if(key==='positions')return {title:'Positions & trade intentions',body:`<h3>Minute-level position health</h3><p>${esc(healthText())}</p><p class="atlas-time">Last recorded review: ${esc(stamp(data.position_health?.last_review?.observed_at))}. A recorded exit trigger is not proof that a position is closed.</p><p>Last recorded owned history. Fresh broker reconciliation is required to confirm current quantities. Showing up to 100 intentions.</p>${table(['Symbol','Origin','State','Owned shares','Entry','Stop','Target'],(history.intents||[]).map(r=>[r.symbol,r.origin==='commissioning'?'Commissioning check':'Strategy',r.state,r.owned_shares,usd(r.entry_usd),usd(r.stop_usd),usd(r.target_usd)]))}`};
    if(key==='history')return {title:'Trade history',body:`<p>Latest 200 owned fills. Commissioning checks are separate from strategy performance. Verified closed commissioning net: ${esc(usd(history.commissioning_net_usd))}.</p>${table(['Time · Stockholm','Symbol','Origin','Side','Shares','Price','Fee'],(history.fills||[]).map(r=>[stamp(r.time_utc),r.symbol,r.origin==='commissioning'?'Commissioning check':'Strategy',r.side,r.shares,usd(r.price_usd),usd(r.fee_usd)]))}`};
    if(key==='activity')return {title:'Activity & daily jobs',body:`<h3>Daily jobs</h3>${table(['Market day','Slot · New York','Result','Started · Stockholm','Finished · Stockholm','Contexts','Decisions','Entry attempts'],(data.jobs||[]).map(r=>[stamp(`${r['Market day']}T12:00:00Z`).split(' · ')[0],r['Slot (New York)']||'10:15',r.Result,stamp(r['Started (UTC)']),stamp(r['Finished (UTC)']),r['Eligible contexts'],r['Analysis decisions'],r['Entry attempts']]))}<h3>Recent activity</h3>${table(['Time · Stockholm','Component','Result','Duration'],(data.activity||[]).map(r=>[stamp(r.time_utc),r.activity,r.result,r.duration_ms===null?'Not recorded':`${(Number(r.duration_ms)/1000).toFixed(1)}s`]))}<h3>Control outcomes</h3>${table(['Requested · Stockholm','Control','Result'],(data.controls||[]).map(r=>[stamp(r['Requested (UTC)']),r.Control,r.Result]))}`};
    if(key==='decisions')return {title:'Decisions',body:`<h3>Today's trade explanation</h3><p data-daily-decision-summary>${esc(data.daily?.decision_summary||'A recorded explanation is not available for this day.')}</p><h3>AI decisions</h3><p>Proposals remain subject to independent risk checks; a proposal is not an order.</p>${table(['Generated · Stockholm','Symbol','Decision','Entry','Stop','Target','Expires · Stockholm'],(data.decisions||[]).map(r=>[stamp(r['Generated (UTC)']),r.Symbol,r.Decision,usd(r['Entry (USD)']),usd(r['Stop (USD)']),usd(r['Target (USD)']),stamp(r['Expires (UTC)'])]))}`};
    if(key==='settings')return {title:'Settings & connection',body:`<p>Read-only. Changes and Stop, Resume or Emergency actions remain on the private VM dashboard.</p><dl class="atlas-detail-list"><dt>Configured allocation</dt><dd>${esc(usd(limits.capital_limit))}</dd><dt>Daily loss cap</dt><dd>${esc(usd(limits.daily_loss_limit))}</dd><dt>Risk per trade</dt><dd>${esc(usd(configured.risk_per_trade))}</dd><dt>Position cap</dt><dd>${esc(usd(configured.max_position_value))}</dd><dt>Maximum positions</dt><dd>${esc(configured.max_positions)}</dd><dt>Reinvestment</dt><dd>${limits.reinvest_profits===true?'Enabled with a cap':'Off'}</dd><dt>Daily schedule</dt><dd>${data.schedule?.enabled===true?'Enabled':'Disabled'} · ${data.schedule?.rescan_minutes===15?'Every 15 minutes, 10:15 AM to before 1 PM New York; flat book only':'10:15 AM New York'}</dd><dt>Broker update</dt><dd>${esc(stamp(data.source_at))}</dd><dt>Portal update</dt><dd>${esc(stamp(data.published_at))}</dd><dt>Display timezone</dt><dd>Stockholm</dd></dl>`};
    if(key==='performance')return {title:'Performance details',body:`<p>Only reconciled closed strategy trades with known fees contribute to strategy metrics.</p><dl class="atlas-detail-list"><dt>Closed strategy trades</dt><dd>${esc(perf.closed_trades??'Unknown')}</dd><dt>Strategy net P&L</dt><dd>${esc(perf.verified===true&&perf.closed_trades>0?usd(perf.net_profit_usd):'Not yet available')}</dd><dt>Win rate</dt><dd>${perf.verified===true&&perf.closed_trades>0?esc(perf.win_rate_percent)+'%':'Not yet available'}</dd><dt>Closed trade drawdown</dt><dd>${esc(perf.verified===true&&perf.closed_trades>0?usd(perf.max_closed_trade_drawdown_usd):'Not yet available')}</dd><dt>Commissioning net</dt><dd>${esc(usd(history.commissioning_net_usd))}</dd></dl><p>Mechanical checks do not establish strategy profitability.</p>`};
    return null;
  }
  function renderModal() {
    if(!modal||!data)return;const content=detailContent(modal);if(!content)return;
    document.getElementById('atlas-dialog-title').textContent=content.title;
    document.getElementById('atlas-dialog-body').innerHTML=content.body;
  }
  function openDetail(key) {
    if(!data||!detailContent(key))return;const dialog=document.getElementById('atlas-live-dialog');if(!dialog)return;
    modal=key;returnFocus=key;renderModal();if(!dialog.open)dialog.showModal();
  }
  function bindDialog() {
    const dialog=document.getElementById('atlas-live-dialog');if(!dialog||dialog.dataset.bound)return;
    dialog.dataset.bound='true';dialog.querySelector('button').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>{modal=null;dialog.querySelector('#atlas-dialog-body').textContent='';if(active&&returnFocus)document.querySelector(`#atlas-live-content [data-detail="${returnFocus}"]`)?.focus({preventScroll:true});});
  }
  document.addEventListener('click',event=>{const button=event.target.closest?.('#atlas-live-content [data-detail]');if(button)openDetail(button.dataset.detail);});
  async function poll(epoch) {
    if (!active || !user || epoch !== generation || document.hidden) return;
    controller = new AbortController(); const current = controller;
    const timeout = setTimeout(()=>current.abort(), 8000);
    try {
      const result = await user.getIdTokenResult();
      if (epoch !== generation || !active) return;
      if (user.email !== 'mithunkurian@gmail.com' || user.emailVerified !== true || result.signInProvider !== 'google.com') throw new Error('auth');
      const response = await fetch(endpoint, {method:'GET', headers:{Authorization:`Bearer ${result.token}`}, cache:'no-store', credentials:'omit', signal:current.signal});
      if (!response.ok) throw new Error('connection');
      const raw = await response.text();
      if (raw.length > 180000) throw new Error('size');
      const documentData = JSON.parse(raw), parsed = JSON.parse(documentData.fields.payload.stringValue);
      if (parsed.schema !== 1 || parsed.scope !== 'NASDAQ_US' || parsed.currency !== 'USD' || parsed.paper_only !== true || !Array.isArray(parsed.history?.intents) || !Array.isArray(parsed.history?.fills)) throw new Error('scope');
      if (epoch !== generation || !active) return;
      data = parsed; revision++; state = 'Private telemetry received'; render();
    } catch (_) {
      if (epoch === generation && active) { data = null; document.getElementById('atlas-live-dialog')?.close(); state = 'Private telemetry unavailable. Sign in with the founder Google account; the VM relay must be online.'; render(); }
    } finally { clearTimeout(timeout); if (controller === current) controller = null; }
  }
  function leave() { active = false; modal=null; renderedRevision=-1; renderedFreshness=null; document.getElementById('atlas-live-dialog')?.close(); const privateBody=document.getElementById('atlas-dialog-body'); if(privateBody)privateBody.textContent=''; generation++; clearInterval(timer); clearInterval(ticker); controller?.abort(); controller = null; data = null; }
  function enter() { leave(); bindDialog(); active = true; state = user ? 'Connecting to private telemetry…' : 'Sign in to view private paper telemetry.'; render(); const epoch = generation; poll(epoch); timer = setInterval(()=>{if (!controller) poll(epoch);},5000); ticker = setInterval(render,1000); }
  function setUser(next) { leave(); user = next; if (location.hash === '#atlas-dashboard') enter(); }
  document.addEventListener('visibilitychange',()=>{ if (active) { data = null; document.getElementById('atlas-live-dialog')?.close(); state = 'Refreshing private telemetry…'; controller?.abort(); render(); if (!document.hidden) { const epoch = ++generation; clearInterval(timer); poll(epoch); timer=setInterval(()=>{if(!controller)poll(epoch);},5000); } } });
  return {view, enter, leave, setUser};
})();
