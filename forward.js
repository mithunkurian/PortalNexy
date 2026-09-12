'use strict';
const PAGE_TITLES={command:'Command Centre',dashboard:'Dashboard',paper:'Paper Trading',risk:'Risk Monitor',logs:'Decision Log',finance:'Finance',boardroom:'Boardroom',roadmap:'Roadmap',todo:'Action Plan',design:'Design Document'};
const forwardState={experiment:null,etf:null,crypto:null,summary:null,dashboard:null,error:null};
let listeners=[],strategyListeners=[],charts=[],activePage='command';
const pendingCommands={};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>v==null||!Number.isFinite(v)?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v);
const stamp=v=>v?new Date(v).toLocaleString(undefined,{timeZone:'UTC',hour12:false})+' UTC':'—';
const fresh=s=>!!s?.updated_at&&Date.now()-new Date(s.updated_at).getTime()>=0&&Date.now()-new Date(s.updated_at).getTime()<180000;
const metric=(label,value)=>`<div class="fp-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
function navigate(id,el){
  if(!PAGE_TITLES[id])return;
  activePage=id;
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id==='page-'+id));
  document.querySelectorAll('.nav-link').forEach(a=>a.classList.toggle('active',a===el||a.getAttribute('onclick')===`navigate('${id}',this)`));
  document.getElementById('page-title').textContent=PAGE_TITLES[id];
  if(id==='roadmap')renderRoadmap();
  if(id==='todo')renderTodos();
  if(id==='design')planScrollSpy();
  renderForward();
}
function tickClock(){const el=document.getElementById('stockholm-clock');if(el)el.textContent='Stockholm '+new Date().toLocaleTimeString('sv-SE',{timeZone:'Europe/Stockholm'});}
function init(){tickClock();renderRoadmap();renderTodos();renderForward();}
setInterval(tickClock,1000);
setInterval(renderForward,30000);
function stopFirestoreListeners(){listeners.forEach(f=>f());strategyListeners.forEach(f=>f());listeners=[];strategyListeners=[];if(typeof closeChat==='function')closeChat();forwardState.etf=null;forwardState.crypto=null;forwardState.experiment=null;forwardState.summary=null;forwardState.dashboard=null;Dashboard.reset(null);renderForward();}
function startFirestoreListeners(){
  stopFirestoreListeners();
  const fail=()=>{forwardState.error='Unable to read experiment data. Check sign-in and the new Firestore rules.';renderForward();};
  listeners.push(db.collection('todos').onSnapshot(s=>{todos=s.docs.map(d=>({id:d.id,...d.data()}));renderTodos();},fail));
  listeners.push(db.collection('forward').doc('current').onSnapshot(s=>{
    forwardState.error=null;
    const experiment=s.exists?s.data().experiment:null;
    if(experiment!==forwardState.experiment){
      strategyListeners.forEach(f=>f());strategyListeners=[];
      forwardState.experiment=experiment;forwardState.etf=null;forwardState.crypto=null;forwardState.summary=null;forwardState.dashboard=null;Dashboard.reset(experiment);
      if(experiment)strategyListeners.push(db.collection('forwardExperiments').doc(experiment).collection('service').doc('dashboard').onSnapshot(doc=>{forwardState.dashboard=doc.exists?doc.data():null;Dashboard.onReport(forwardState.dashboard);renderForward();},fail));
      if(experiment)strategyListeners.push(db.collection('forwardExperiments').doc(experiment).collection('service').doc('summary').onSnapshot(doc=>{forwardState.summary=doc.exists?doc.data():null;renderForward();},fail));
      if(experiment)for(const strategy of ['etf','crypto'])strategyListeners.push(db.collection('forwardExperiments').doc(experiment).collection('strategies').doc(strategy).onSnapshot(doc=>{
        forwardState[strategy]=doc.exists?doc.data():null;
        const pending=pendingCommands[strategy];
        if(pending&&forwardState[strategy]?.last_command?.id===pending.id)delete pendingCommands[strategy];
        renderForward();
      },fail));
    }
    renderForward();
  },fail));
}
async function paperControl(strategy,action){
  const s=forwardState[strategy];
  if(!forwardState.experiment||!fresh(s)||pendingCommands[strategy])return;
  const id=crypto.randomUUID();pendingCommands[strategy]={id,time:Date.now()};renderForward();
  try{await db.collection('forwardExperiments').doc(forwardState.experiment).collection('commands').doc(strategy).set({id,action,issued_at:firebase.firestore.FieldValue.serverTimestamp()});}
  catch(e){delete pendingCommands[strategy];forwardState.error='Command could not be saved. Check sign-in and Firestore rules.';renderForward();}
}
function portfolioMetrics(s){const p=s?.portfolio;return `<div class="fp-metrics">${metric('Equity',money(p?.equity))}${metric('Allocated cash',money(p?.cash))}${metric('Realised P&L, net costs',money(p?.realised))}${metric('Unrealised P&L',money(p?.unrealised))}${metric('Reported costs',money(p?.costs))}${metric('Current drawdown',s?.drawdown==null?'—':s.drawdown.toFixed(2)+'%')}${metric('Maximum drawdown',s?.max_drawdown==null?'—':s.max_drawdown.toFixed(2)+'%')}${metric('Buy & hold reference',money(s?.benchmark))}</div>`;}
function combined(){
  const summary=forwardState.summary;
  if(summary){const valid=fresh(summary)&&fresh(forwardState.etf)&&fresh(forwardState.crypto)&&!forwardState.etf?.valuation_stale&&!forwardState.crypto?.valuation_stale;return {...summary,portfolio:valid?summary.portfolio:null,benchmark:valid?summary.benchmark:null,drawdown:valid?summary.drawdown:null,max_drawdown:valid?summary.max_drawdown:null};}
  const a=forwardState.etf,b=forwardState.crypto;
  const valid=a?.portfolio&&b?.portfolio&&a.inception&&b.inception&&!a.valuation_stale&&!b.valuation_stale&&fresh(a)&&fresh(b);
  const p=valid?Object.fromEntries(['equity','cash','realised','unrealised','costs'].map(k=>[k,a.portfolio[k]==null||b.portfolio[k]==null?null:a.portfolio[k]+b.portfolio[k]])):null;
  const history=combinedHistory(a,b);
  let peak=null,drawdown=null,max=0;
  for(const point of history){peak=Math.max(peak??point.equity,point.equity);drawdown=(point.equity/peak-1)*100;max=Math.min(max,drawdown);}
  return {portfolio:p,benchmark:valid?a.benchmark+b.benchmark:null,drawdown:valid?drawdown:null,max_drawdown:valid&&history.length?max:null,history};
}
function combinedHistory(a,b){
  if(!a?.history?.length||!b?.history?.length)return [];
  // Only sum observations within the same five-minute sample window; no interpolation/backfill.
  const bucket=t=>Math.floor(new Date(t).getTime()/300000);
  const lookup=new Map(b.history.map(p=>[bucket(p.time),p]));
  return a.history.filter(p=>lookup.has(bucket(p.time))).map(p=>{const q=lookup.get(bucket(p.time));return {time:p.time,equity:p.equity+q.equity,benchmark:p.benchmark+q.benchmark};});
}
function table(headers,rows,empty){return `<div class="fp-table-wrap"><table class="fp-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}" class="fp-muted">${esc(empty)}</td></tr>`}</tbody></table></div>`;}
function strategyCard(id){
  const s=forwardState[id],title=id==='etf'?'ETF rotation':'BTC / ETH momentum';
  const version=s?.version||(id==='etf'?'etf-rotation-1.0.0':'crypto-momentum-1.0.0');
  const pending=pendingCommands[id];
  if(pending&&Date.now()-pending.time>120000){delete pendingCommands[id];forwardState.error='Command acknowledgement timed out. Check service status before retrying.';}
  const controls=!!s&&fresh(s)&&!pendingCommands[id];
  const rule=id==='etf'?'SPY · EFA · EEM · TLT · GLD. Positive 126-session momentum and above the 200-session average. Top two, equally weighted. Evaluate after the first NYSE session of each month; execute in the following session.':'BTC/USD · ETH/USD. Positive 90-day momentum and above the 200-day average. Strongest qualifying asset. Evaluate at 00:05 UTC using the completed prior UTC day.';
  const p=s?.portfolio;
  return `<section class="fp-card"><div style="display:flex;justify-content:space-between;gap:10px;align-items:start"><h2>${title}</h2><span class="fp-tag">${esc(s?.mode?.replace('_',' ')||'Not started')}</span></div><span class="fp-tag">${esc(version)} · frozen at inception</span><p class="fp-rules" style="margin-top:12px">${rule} Otherwise cash. Long-only, no leverage, 98% exposure cap with 2% cash reserve; profits reinvested.</p>
    ${!fresh(s)?'<div class="fp-error">Awaiting service connection. No current broker status is available.</div>':''}
    ${s?.error?`<div class="fp-error">${esc(s.error)}</div>`:''}
    ${s?.valuation_stale?'<div class="fp-error">Last known valuation — stale or unreconciled. Excluded from combined current totals.</div>':''}
    <div class="fp-actions"><button onclick="paperControl('${id}','start')" ${!controls||s?.inception?'disabled':''}>Start experiment</button><button class="secondary" onclick="paperControl('${id}','pause')" ${!controls||s?.mode==='paused'?'disabled':''}>Pause</button><button class="secondary" onclick="paperControl('${id}','resume')" ${!controls||!s?.inception||s?.mode!=='paused'?'disabled':''}>Resume</button></div>
    <p class="fp-muted">Pause stops new strategy submissions. Existing holdings stay invested; outstanding orders remain at the broker and may fill. Fills continue to reconcile. Missed evaluations are recorded, never backfilled.</p>
    ${pendingCommands[id]?'<p role="status" class="fp-muted">Waiting for service acknowledgement…</p>':''}
    ${s?.last_command?`<p class="fp-muted">Last control: ${esc(s.last_command.status)}</p>`:''}
    ${id==='crypto'?'<p class="fp-muted">Explicit execution route: Alpaca paper, direct BTC/ETH. IBKR crypto capability is account-specific and has not been certified by this workspace.</p>':''}
    ${s?.crypto_capability?`<p class="fp-muted">IBKR crypto preflight: ${esc(Object.entries(s.crypto_capability).map(([symbol,result])=>symbol+': '+result).join(' · '))}</p>`:''}
    ${portfolioMetrics(s)}
    <div class="fp-chart"><canvas id="chart-${id}" aria-label="${title} forward equity versus buy and hold"></canvas></div>
    <p class="fp-muted">${id==='etf'?'Equal-weight five-ETF':'50/50 BTC/ETH'} buy-and-hold reference starts at observed inception quotes. Reference excludes trading fees and distributions; it is not a broker position or historical profit. ${s?.costs_provisional||p?.costs_pending?'Costs remain provisional until broker fee reporting completes.':''}</p>
    <dl class="fp-meta">${[['Broker',s?.broker||(id==='etf'?'IBKR paper':'Alpaca paper crypto')],['Paper account',s?.account||'Not configured'],['Connection',fresh(s)?s?.connection:'Unknown / stale'],['Inception',stamp(s?.inception)],['Data timestamp',stamp(s?.data_timestamp)],['Data mode',s?.quotes?Object.values(s.quotes).some(q=>q.delayed)?'Delayed — orders blocked':'Real-time broker feed':'Not verified'],['Last successful cycle',stamp(s?.last_success)],['Next evaluation',stamp(s?.next_evaluation)],['Next execution',stamp(s?.next_execution)],['Last reconciliation',stamp(s?.last_reconciled)],['Broker USD cash',money(s?.broker_snapshot?.cash)],['Reconciliation',s?.reconciliation||'Not verified'],['Execution',s?.execution_state||'Awaiting evaluation']].map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl>
    <h3>Attributed positions</h3>${table(['Symbol','Quantity','Market value'],(p?.positions||[]).map(p=>[p.symbol,p.quantity,money(p.market_value)]),s?.inception?'No attributed holdings':'No experiment has started')}
    <h3>Orders</h3>${table(['Symbol / side','Quantity','Filled','Broker status'],(s?.orders||[]).slice(-12).map(o=>[o.symbol+' / '+o.side,o.quantity,o.filled??'Awaiting report',o.status]),'No experiment orders')}
    <h3>Confirmed fills</h3>${table(['Time (UTC)','Symbol / side','Quantity','Price','Fee'],(s?.fills||[]).slice(-12).map(f=>[stamp(f.time),f.symbol+' / '+f.side,f.quantity,money(f.price),f.fee==null?'Pending':money(f.fee)]),'No confirmed forward fills')}
  </section>`;
}
function logs(){const entries=['etf','crypto'].flatMap(s=>(forwardState[s]?.events||[]).map(e=>({...e,strategy:s}))).sort((a,b)=>b.time.localeCompare(a.time));return entries.length?entries.map(e=>`<article class="fp-log"><strong>${esc(e.strategy.toUpperCase()+' · '+e.kind.replaceAll('_',' '))}</strong><div class="fp-muted">${esc(stamp(e.time))}</div><pre>${esc(JSON.stringify(e.detail,null,2))}</pre></article>`).join(''):'<p class="fp-muted">No forward decisions yet. Historical trading logs are excluded.</p>';}
function draw(id,history){const canvas=document.getElementById(id);if(!canvas)return;if(!history.length){canvas.parentElement.style.height='64px';canvas.parentElement.innerHTML='<p class=fp-muted>No forward equity observations yet.</p>';return;}if(typeof Chart==='undefined')return;charts.push(new Chart(canvas,{type:'line',data:{labels:history.map(p=>stamp(p.time)),datasets:[{label:'Forward equity',data:history.map(p=>p.equity),borderColor:'#182053',backgroundColor:'#18205312',fill:true,pointRadius:0,borderWidth:2},{label:'Buy & hold reference',data:history.map(p=>p.benchmark),borderColor:'#8492b5',borderDash:[5,4],pointRadius:0,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{position:'bottom'}},scales:{x:{display:false},y:{ticks:{callback:v=>'$'+v}}}}}));}
function renderForward(){
  if(!document.getElementById('forward-paper'))return;
  charts.forEach(c=>c.destroy());charts=[];
  const aggregate=combined();
  const banner=`<div class="fp-banner"><div><strong>${forwardState.experiment?esc(forwardState.experiment):'Ready for a new forward test'}</strong><p>${forwardState.experiment?'Paper execution only · USD accounting · no historical simulated profits':'Connect the background service and verify paper accounts before starting.'}</p></div><span class="fp-tag" style="color:#182053">Forward paper</span></div>`;
  const error=forwardState.error?`<div class="fp-error" role="alert">${esc(forwardState.error)}</div>`:'';
  const combinedCard=`<section class="fp-card"><h2>Combined experiment</h2><p class="fp-muted">Sum of strategy allocations, not separate broker accounts. Unallocated account cash and historical positions are excluded. Both strategies need fresh, reconciled valuations.</p>${portfolioMetrics(aggregate)}${table(['Strategy','Symbol','Quantity','Market value'],(aggregate.portfolio?.positions||[]).map(p=>[p.strategy,p.symbol,p.quantity,money(p.market_value)]),'No combined reconciled positions available')}<div class="fp-chart"><canvas id="chart-combined" aria-label="Combined forward equity and reference"></canvas></div><p class="fp-muted">Chart shows up to 500 recent matched observations. Combined drawdown uses all matched observations since both strategies started. Full records remain in the service ledger and Firestore history.</p></section>`;
  let html='';
  if(activePage==='dashboard')html=Dashboard.render();
  else if(['paper','finance','command'].includes(activePage)){
    html=banner+error+combinedCard;
    if(activePage==='paper')html+=`<div class="fp-grid">${strategyCard('etf')}${strategyCard('crypto')}</div><section class="fp-card"><h2>Decision journal</h2>${logs()}</section>`;
    else html+=`<div class="fp-grid">${['etf','crypto'].map(id=>`<section class="fp-card"><h2>${id==='etf'?'ETF rotation':'BTC / ETH momentum'}</h2><p class="fp-muted">${esc(forwardState[id]?.version||'Awaiting experiment')} · ${esc(fresh(forwardState[id])?forwardState[id]?.connection:'Awaiting service')}</p>${portfolioMetrics(forwardState[id])}${forwardState[id]?.error?`<p class="fp-error">${esc(forwardState[id].error)}</p>`:''}<button class="fp-button" onclick="navigate('paper')">Open Paper Trading</button></section>`).join('')}</div>`;
  } else if(activePage==='logs')html=error+`<section class="fp-card">${logs()}</section>`;
  else if(activePage==='risk')html=error+`<section class="fp-card"><h2>Execution gates</h2><p class="fp-rules">Exact paper-account allowlists · server-side credentials · verified contract, currency and exchange · trading permission preflight · fresh bid/ask · eligible session · cash and fee reserve · long-only sizing · durable duplicate prevention · broker reconciliation · service ownership lease.</p><p class="fp-muted">No fixed annual-return target or portfolio drawdown rejection threshold. Any reconciliation discrepancy or uncertain submission blocks new orders; it does not liquidate holdings or cancel broker orders.</p>${table(['Strategy','Reconciliation','Last checked','Error'],['etf','crypto'].map(id=>[id,forwardState[id]?.reconciliation||'Unverified',stamp(forwardState[id]?.last_reconciled),forwardState[id]?.error||'—']),'')}</section>`;
  const container=document.getElementById('forward-'+activePage);if(container)container.innerHTML=html;
  if(container){draw('chart-combined',aggregate.history);if(activePage==='paper')for(const id of ['etf','crypto'])draw('chart-'+id,forwardState[id]?.history||[]);}
  const strip=document.getElementById('system-status-strip');if(strip)strip.innerHTML=['etf','crypto'].map(id=>`<div class="fp-muted">${id==='etf'?'IBKR ETF':'Alpaca crypto'}: ${esc(fresh(forwardState[id])?forwardState[id]?.connection||'Unverified':'Awaiting service')}</div>`).join('');
  const badge=document.getElementById('active-runtime-badge');if(badge)badge.textContent='Forward paper · '+(fresh(forwardState.etf)||fresh(forwardState.crypto)?'Service reporting':'Awaiting service');
}
