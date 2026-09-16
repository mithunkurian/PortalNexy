'use strict';
const HomepageWIP=(()=>{
  let strategy='all',period='week',view='positions',selected=null,technical=false;
  const labels={today:'Today',week:'This week',month:'This month',all:'All time'};
  const names={etf:'ETF rotation',crypto:'BTC / ETH momentum'};
  const start=key=>Dashboard.start(key);
  const states=()=> (strategy==='all'?['etf','crypto']:[strategy]).map(id=>({id,s:forwardState[id]}));
  const usable=s=>s?.inception&&fresh(s)&&!s.valuation_stale&&s.portfolio;
  const sum=(items,key)=>items.length?items.reduce((total,{s})=>total+(s.portfolio?.[key]||0),0):null;
  const select=(key,value)=>{if(key==='strategy'&&['all','etf','crypto'].includes(value))strategy=value;if(key==='period'&&labels[value])period=value;if(key==='view'&&['positions','orders','fills'].includes(value))view=value;selected=null;renderForward();};
  const detail=index=>{selected=selected===index?null:index;renderForward();};
  const toggleTechnical=()=>{technical=!technical;renderForward();};
  const dropdown=(label,key,options,value)=>`<label>${esc(label)}<select aria-label="${esc(label)}" onchange="HomepageWIP.select('${key}',this.value)">${options.map(([k,v])=>`<option value="${k}" ${k===value?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
  function render(){
    const chosen=states(),reporting=chosen.filter(({s})=>usable(s));
    const currentEquity=sum(reporting,'equity');
    const cash=sum(reporting,'cash'),unrealised=sum(reporting,'unrealised'),realised=sum(reporting,'realised');
    const pnl=realised==null||unrealised==null?null:realised+unrealised;
    const positions=chosen.flatMap(({id,s})=>(s?.portfolio?.positions||[]).map(p=>({...p,strategy:id,status:usable(s)?'Reconciled':'Stale'})));
    const orders=chosen.flatMap(({id,s})=>(s?.orders||[]).filter(Dashboard.waiting).map(o=>({...o,strategy:id})));
    const fills=chosen.flatMap(({id,s})=>(s?.fills||[]).map(f=>({...f,strategy:id}))).filter(f=>!start(period)||new Date(f.time)>=start(period)).sort((a,b)=>b.time.localeCompare(a.time));
    const todayStart=Dashboard.start('today'),todayHistory=(strategy==='all'?combined().history:forwardState[strategy]?.history||[]).filter(p=>new Date(p.time)>=todayStart);
    const todayPnl=currentEquity!=null&&todayHistory.length?currentEquity-todayHistory[0].equity:null;
    const history=(strategy==='all'?combined().history:forwardState[strategy]?.history||[]).filter(p=>!start(period)||new Date(p.time)>=start(period));window.homeWipHistory=history;
    const latest=Math.max(...chosen.map(({s})=>s?.updated_at?new Date(s.updated_at).getTime():0));
    const next=chosen.flatMap(({s})=>[s?.next_evaluation,s?.next_execution].filter(Boolean)).sort()[0];
    const issues=[];
    chosen.forEach(({id,s})=>{if(!fresh(s))issues.push(`${names[id]} service status is stale`);else if(s.error)issues.push(`${names[id]}: ${s.error}`);else if(s.mode==='paused')issues.push(`${names[id]} is paused`);});
    if(orders.some(o=>o.reprice_count>0))issues.push('One or more open orders have required repricing');
    const source=view==='positions'?positions:view==='orders'?orders:fills;
    const row=selected==null?null:source[selected];
    const activityHeaders=view==='positions'?['Asset','Strategy','Quantity','Market value','Status']:view==='orders'?['Asset / side','Strategy','Quantity','Filled','Status']:['Asset / side','Strategy','Quantity','Price','Time'];
    const values=r=>view==='positions'?[r.symbol,names[r.strategy],r.quantity,money(r.market_value),r.status]:view==='orders'?[r.symbol+' / '+r.side,names[r.strategy],r.quantity,r.filled||0,r.status]:[r.symbol+' / '+r.side,names[r.strategy],r.quantity,money(r.price),stamp(r.time)];
    const events=chosen.flatMap(({id,s})=>(s?.events||[]).map(e=>({...e,strategy:id}))).sort((a,b)=>b.time.localeCompare(a.time)).slice(0,3);
    const maxDrawdown=reporting.length?Math.min(...reporting.map(({s})=>s.max_drawdown??0)):null;
    return `<div class="home-wip">
      <section class="hw-status"><div><span class="hw-live ${issues.length?'warn':'ready'}"></span><strong>Paper trading ${issues.length?'needs attention':'is reporting'}</strong><small>${latest?`Updated ${Math.max(0,Math.round((Date.now()-latest)/1000))} seconds ago`:'No service update'}</small></div><div><small>Next scheduled action</small><strong>${next?stamp(next):'Awaiting schedule'}</strong></div></section>
      ${issues.length?`<section class="hw-alert"><span class="material-symbols-outlined">warning</span><div><strong>Attention required</strong>${issues.map(x=>`<p>${esc(x)}</p>`).join('')}</div></section>`:''}
      <div class="hw-heading"><div><span>PAPER TRADING HOME</span><h2>Portfolio health at a glance</h2></div><div class="hw-filters">${dropdown('Strategy','strategy',[['all','All strategies'],['etf','ETF rotation'],['crypto','BTC / ETH']],strategy)}${dropdown('Time frame','period',Object.entries(labels),period)}</div></div>
      <section class="hw-kpis">${metric('Allocated equity',money(currentEquity))}${metric('Total P&L',money(pnl))}${metric("Today's P&L",money(todayPnl))}${metric('Strategy cash',money(cash))}${metric('Drawdown',maxDrawdown==null?'—':maxDrawdown.toFixed(2)+'%')}${metric('Open positions',positions.length)}${metric('Waiting orders',orders.length)}</section>
      <div class="hw-main"><section class="fp-card hw-chart"><div class="hw-card-title"><div><h2>Equity performance</h2><p>${labels[period]} · observed forward results</p></div><span>${reporting.length}/${chosen.length} strategies current</span></div><div class="fp-chart"><canvas id="chart-home-wip" aria-label="Homepage forward equity versus buy and hold"></canvas></div></section>
      <div class="hw-strategies">${['etf','crypto'].map(id=>{const s=forwardState[id],p=s?.portfolio,pos=p?.positions||[],last=s?.events?.[0],sp=p?.realised==null||p?.unrealised==null?null:p.realised+p.unrealised;return `<section class="fp-card"><div class="hw-card-title"><h2>${names[id]}</h2><span class="hw-pill ${s?.error?'warn':s?.mode==='running'?'ready':''}">${esc(s?.error?'Blocked':(s?.mode||'Waiting').replaceAll('_',' '))}</span></div><strong class="hw-holding">${pos.length?pos.map(x=>`${x.symbol} · ${x.quantity}`).join('<br>'):'Cash / no position'}</strong><div class="hw-strategy-meta"><span>Equity <b>${money(p?.equity)}</b></span><span>P&L <b>${money(sp)}</b></span></div><p>${esc(last?last.kind.replaceAll('_',' '):'Awaiting first decision')} · ${esc(s?.version||'Rule not loaded')}</p><small>Next: ${esc(s?.next_evaluation?stamp(s.next_evaluation):'Awaiting eligible evaluation')}</small></section>`}).join('')}</div></div>
      <section class="fp-card hw-activity"><div class="hw-tabs">${[['positions','Active positions',positions.length],['orders','Waiting orders',orders.length],['fills','Recent fills',fills.length]].map(([k,l,n])=>`<button aria-selected="${view===k}" onclick="HomepageWIP.select('view','${k}')">${l}<span>${n}</span></button>`).join('')}</div><div class="fp-table-wrap"><table class="fp-table"><thead><tr>${activityHeaders.map(h=>`<th>${esc(h)}</th>`).join('')}<th>Details</th></tr></thead><tbody>${source.length?source.slice(0,6).map((r,i)=>`<tr>${values(r).map(v=>`<td>${esc(v)}</td>`).join('')}<td><button class="hw-view" onclick="HomepageWIP.detail(${i})">${selected===i?'Close':'View'}</button></td></tr>`).join(''):`<tr><td class="hw-empty" colspan="${activityHeaders.length+1}">No ${esc(view)} to display</td></tr>`}</tbody></table></div>${row?`<div class="hw-detail">${Object.entries(row).filter(([k,v])=>!['strategy','detail'].includes(k)&&typeof v!=='object').slice(0,8).map(([k,v])=>`<div><small>${esc(k.replaceAll('_',' '))}</small><strong>${esc(v)}</strong></div>`).join('')}</div>`:''}</section>
      <div class="hw-bottom"><section class="fp-card"><div class="hw-card-title"><h2>Latest decisions</h2><button onclick="navigate('logs')">Open full log</button></div>${events.length?events.map(e=>`<article class="hw-event"><span>${esc(e.strategy.toUpperCase())}</span><div><strong>${esc(e.kind.replaceAll('_',' '))}</strong><small>${stamp(e.time)}</small></div></article>`).join(''):'<p class="fp-muted">No forward decisions published yet.</p>'}</section>
      <section class="fp-card"><div class="hw-card-title"><h2>System details</h2><button onclick="HomepageWIP.toggleTechnical()">${technical?'Hide':'Show'}</button></div>${technical?chosen.map(({id,s})=>`<dl class="hw-tech"><dt>${names[id]}</dt><dd>${esc(s?.account||'No account')}</dd><dt>Connection</dt><dd>${esc(fresh(s)?s?.connection||'Unverified':'Stale')}</dd><dt>Reconciled</dt><dd>${esc(stamp(s?.last_reconciled))}</dd><dt>Execution</dt><dd>${esc(s?.execution_policy||'Not loaded')}</dd></dl>`).join(''):'<p class="fp-muted">Account IDs, timestamps, reconciliation and execution policies are collapsed by default.</p>'}</section></div>
    </div>`;
  }
  return {render,select,detail,toggleTechnical};
})();
if(typeof module!=='undefined')module.exports=HomepageWIP;
