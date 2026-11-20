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
  function view() { return `<section class="page-intro"><p class="eyebrow">ATLAS / PRIVATE PAPER MONITOR</p><h1>ATLAS Dashboard</h1><p>NASDAQ · USD · paper trading</p></section><div id="atlas-live-content" aria-live="polite"></div>`; }
  function render() {
    const target = document.getElementById('atlas-live-content');
    if (!target) return;
    if (!data) { target.innerHTML = `<section class="panel"><h2>Private connection</h2><p role="status">${esc(state)}</p></section>`; return; }
    const relayFresh = age(data.published_at) >= -2 && age(data.published_at) <= 30;
    const sourceFresh = relayFresh && data.source_valid === true && age(data.source_at) >= -2 && age(data.source_at) <= 15;
    const label = !relayFresh ? 'Telemetry offline / stale' : !sourceFresh ? 'Broker source unavailable / stale' : data.execution_enabled ? 'Paper entries armed' : 'Paper entries paused';
    const history = data.history || {}, perf = history.performance || {}, limits = data.limits || {}, configured = limits.configured_limits || {};
    const money = sourceFresh ? data.money || {} : {};
    const intents = Array.isArray(history.intents) ? history.intents : [], fills = Array.isArray(history.fills) ? history.fills : [];
    const strategy = intents.filter(r=>r.origin==='strategy'), mechanics = intents.filter(r=>r.origin==='commissioning');
    const metric = (name, value, note) => `<article class="panel atlas-metric"><span>${esc(name)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
    target.innerHTML = `<section class="panel atlas-connection"><div><p class="eyebrow">${esc(label)}</p><h2>${sourceFresh ? 'Connected to ATLAS' : 'Current financial values unknown'}</h2><p>Source: ${esc(data.source_at || 'Unknown')} · Relay: ${esc(data.published_at)}</p><p>${esc(state)} · Mode: ${esc(data.mode)} · Phase: ${esc(data.phase)} · Regular session: ${sourceFresh ? data.session_open === true ? 'Open' : data.session_open === false ? 'Closed' : 'Unknown' : 'Unknown'}</p></div><span class="pill">Read-only</span></section>
      <div class="atlas-metrics">${metric('Allocated capital',usd(money.strategy_capital_usd),'Verified current allocation')}${metric('Owned daily P&L',usd(money.owned_day_pnl_usd),'Includes known owned fees')}${metric('Open exposure',usd(money.owned_exposure_usd),'ATLAS-owned positions')}${metric('Open risk',usd(money.owned_open_risk_usd),'Independent current policy')}</div>
      <section class="panel"><h2>Strategy performance</h2><p>${esc(strategy.length)} strategy intentions recorded · ${esc(perf.closed_trades ?? 'Unknown')} closed strategy trades · Net ${esc(perf.verified === true && perf.closed_trades > 0 ? usd(perf.net_profit_usd) : 'Unknown')}</p><p>${esc(mechanics.length)} commissioning intentions and ${esc(history.total_fills ?? 'Unknown')} total owned fills are recorded separately. Verified closed commissioning net: ${esc(usd(history.commissioning_net_usd))}. Mechanical checks do not establish strategy profitability.</p></section>
      <section class="panel"><h2>Positions & trade intentions</h2><p>Last recorded history; open quantities require fresh broker reconciliation. Showing up to 100 intentions.</p>${table(['Symbol','Origin','State','Owned shares','Entry','Stop','Target'],intents.map(r=>[r.symbol,r.origin,r.state,r.owned_shares,usd(r.entry_usd),usd(r.stop_usd),usd(r.target_usd)]))}</section>
      <section class="panel"><h2>Owned fills</h2><p>Latest 200 fills · known fees shown per execution.</p>${table(['UTC time','Symbol','Origin','Side','Shares','Price','Fee'],fills.map(r=>[r.time_utc,r.symbol,r.origin,r.side,r.shares,usd(r.price_usd),usd(r.fee_usd)]))}</section>
      <section class="panel"><h2>Configured limits & schedule</h2><p>Configured allocation ${esc(usd(limits.capital_limit))} · Daily loss cap ${esc(usd(limits.daily_loss_limit))} · Trade risk ${esc(usd(configured.risk_per_trade))} · Position cap ${esc(usd(configured.max_position_value))} · Maximum positions ${esc(configured.max_positions)} · Reinvestment ${limits.reinvest_profits === true ? 'enabled with cap' : 'off'}</p><p>Daily schedule ${data.schedule?.enabled === true ? 'enabled' : 'disabled'} · ${esc(data.schedule?.run_time)} ${esc(data.schedule?.timezone)}. Each run still requires fresh sources and independent risk acceptance; missed windows are not replayed.</p><p>Stop, Resume, Emergency and limit editing remain on the private VM dashboard.</p></section>
      <section class="panel"><h2>Daily jobs</h2>${table(['Day','Result','Contexts','Decisions','Entry attempts'],(data.jobs || []).map(r=>[r['Market day'],r.Result,r['Eligible contexts'],r['Analysis decisions'],r['Entry attempts']]))}</section>
      <section class="panel"><h2>Recent control outcomes</h2>${table(['Requested UTC','Control','Result'],(data.controls || []).map(r=>[r['Requested (UTC)'],r.Control,r.Result]))}</section>
      <section class="panel"><h2>Recent activity</h2>${table(['UTC time','Component','Result','Duration ms'],(data.activity || []).map(r=>[r.time_utc,r.activity,r.result,r.duration_ms]))}</section>
      <section class="panel"><h2>Analysis decisions</h2>${table(['Generated UTC','Symbol','Decision','Entry','Stop','Target'],(data.decisions || []).map(r=>[r['Generated (UTC)'],r.Symbol,r.Decision,usd(r['Entry (USD)']),usd(r['Stop (USD)']),usd(r['Target (USD)'])]))}</section>`;
  }
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
      data = parsed; state = 'Private telemetry received'; render();
    } catch (_) {
      if (epoch === generation && active) { data = null; state = 'Private telemetry unavailable. Sign in with the founder Google account; the VM relay must be online.'; render(); }
    } finally { clearTimeout(timeout); if (controller === current) controller = null; }
  }
  function leave() { active = false; generation++; clearInterval(timer); clearInterval(ticker); controller?.abort(); controller = null; data = null; }
  function enter() { leave(); active = true; state = user ? 'Connecting to private telemetry…' : 'Sign in to view private paper telemetry.'; render(); const epoch = generation; poll(epoch); timer = setInterval(()=>{if (!controller) poll(epoch);},5000); ticker = setInterval(render,1000); }
  function setUser(next) { leave(); user = next; if (location.hash === '#atlas-dashboard') enter(); }
  document.addEventListener('visibilitychange',()=>{ if (active) { data = null; state = 'Refreshing private telemetry…'; controller?.abort(); render(); if (!document.hidden) { const epoch = ++generation; clearInterval(timer); poll(epoch); timer=setInterval(()=>{if(!controller)poll(epoch);},5000); } } });
  return {view, enter, leave, setUser};
})();
