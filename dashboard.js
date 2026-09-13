'use strict';
// Read-only view: broker actions remain exclusively in Paper Trading.
const Dashboard=(()=>{
  const labels={today:'Today',week:'This week',month:'This month',days30:'Last 30 days',all:'All time'};
  let view='positions',symbol='all',side='all',status='all',page=0,selected=null;
  let period='today',strategy='all',experiment=null,rows=[],cursor=null,more=false,loading=false,error='',generation=0,loadedAt=null,fillCount=null;
  function start(key,now=new Date()){
    const d=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()));
    if(key==='all')return null;
    if(key==='week')d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);
    if(key==='month')d.setUTCDate(1);
    if(key==='days30')d.setUTCDate(d.getUTCDate()-29);
    return d;
  }
  const waiting=o=>!['filled','cancelled','rejected'].includes(o.status);
  const name=s=>s==='etf'?'ETF rotation':'BTC / ETH';
  function reset(value){page=0;selected=null;symbol=side=status='all';experiment=value;generation++;rows=[];cursor=null;more=false;loading=false;error='';loadedAt=null;fillCount=null;}
  function onReport(report){
    const next=report?.periods?.all?.all?.fills;
    if(next!=null&&next!==fillCount){fillCount=next;generation++;loading=false;loadedAt=null;rows=[];cursor=null;more=false;error='';}
  }
  async function load(append=false){
    if(!experiment||loading)return;
    const token=++generation;loading=true;error='';
    if(!append){rows=[];cursor=null;more=false;page=0;selected=null;}renderForward();
    try{
      let q=db.collection('forwardExperiments').doc(experiment).collection('fills').orderBy('time','desc');
      const lower=start(period);
      if(lower)q=q.where('time','>=',lower.toISOString().replace('.000Z','+00:00'));
      if(append&&cursor)q=q.startAfter(cursor);
      const result=await q.limit(100).get();
      if(token!==generation)return;
      rows=rows.concat(result.docs.map(d=>d.data()));cursor=result.docs.at(-1)||cursor;more=result.docs.length===100;loadedAt=new Date().toISOString();
    }catch(e){if(token===generation)error='Could not load the fill archive. Check connection and refresh.';}
    finally{if(token===generation){loading=false;renderForward();}}
  }
  function select(key){if(!labels[key])return;period=key;page=0;selected=null;generation++;loading=false;load();renderForward();}
  function selectStrategy(value){if(!['all','etf','crypto'].includes(value))return;strategy=value;symbol=side=status='all';page=0;selected=null;renderForward();}
  function filter(key,value){
    if(key==='view'&&['positions','waiting','fills'].includes(value)){view=value;symbol=side=status='all';}
    else if(key==='symbol')symbol=value;
    else if(key==='side')side=value;
    else if(key==='status')status=value;
    page=0;selected=null;renderForward();
  }
  function turn(delta){page=Math.max(0,page+delta);selected=null;renderForward();}
  function detail(index){selected=selected===index?null:index;renderForward();}
  function dropdown(label,key,options,value){return `<label>${esc(label)}<select aria-label="${esc(label)}" onchange="Dashboard.${key==='period'?'select(this.value)':key==='strategy'?'selectStrategy(this.value)':`filter('${key}',this.value)`}">${options.map(([k,v])=>`<option value="${esc(k)}" ${k===value?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;}
  function render(){
    if(experiment!==forwardState.experiment)reset(forwardState.experiment);
    if(experiment&&!loadedAt&&!loading&&!error)queueMicrotask(()=>load());
    const states=(strategy==='all'?['etf','crypto']:[strategy]).map(id=>({id,s:forwardState[id]}));
    const valid=states.every(({s})=>s?.inception&&fresh(s)&&!s.valuation_stale&&s.portfolio);
    const sum=k=>valid?states.reduce((a,{s})=>a+s.portfolio[k],0):null;
    const summary=forwardState.dashboard;
    const sameDay=summary?.updated_at&&new Date(summary.updated_at).toISOString().slice(0,10)===new Date().toISOString().slice(0,10);
    const activity=sameDay?summary?.periods?.[period]?.[strategy]:null;
    const positions=states.flatMap(({id,s})=>(s?.portfolio?.positions||[]).map(p=>({...p,strategy:id,status:fresh(s)&&!s.valuation_stale?'Reconciled':'Last known / stale'})));
    const orders=states.flatMap(({id,s})=>(s?.orders||[]).filter(waiting).map(o=>({...o,strategy:id,dataStatus:fresh(s)?'Service reporting':'Last known / stale'})));
    const fills=rows.filter(f=>(strategy==='all'||f.strategy===strategy)&&forwardState[f.strategy]?.inception&&new Date(f.time)>=new Date(forwardState[f.strategy].inception)&&new Date(f.time)<=new Date()&&(!start(period)||new Date(f.time)>=start(period))).map(f=>({...f,status:f.order_status||'Unknown'}));
    const source=view==='positions'?positions:view==='waiting'?orders:fills;
    const options=key=>[['all',key==='status'?'All statuses':key==='symbol'?'All assets':'All '+key+'s'],...[...new Set(source.map(r=>r[key]).filter(Boolean))].sort().map(v=>[v,v])];
    const records=source.filter(r=>(symbol==='all'||r.symbol===symbol)&&(view==='positions'||side==='all'||r.side===side)&&(status==='all'||r.status===status));
    page=Math.min(page,Math.max(0,Math.ceil(records.length/5)-1));
    const visible=records.slice(page*5,page*5+5);
    const headers=view==='positions'?['Asset','Strategy','Quantity','Market value','Status']:view==='waiting'?['Asset / side','Strategy','Quantity','Filled','Status']:['Asset / side','Strategy','Quantity','Price','Filled (UTC)'];
    const values=r=>view==='positions'?[r.symbol,name(r.strategy),r.quantity,money(r.market_value),r.status]:view==='waiting'?[r.symbol+' / '+r.side,name(r.strategy),r.quantity,r.filled??'Unconfirmed',r.status]:[r.symbol+' / '+r.side,name(r.strategy),r.quantity,money(r.price),stamp(r.time)];
    const picked=selected==null?null:records[selected];
    const fields=picked?Object.entries(view==='positions'?{'Asset':picked.symbol,'Strategy':name(picked.strategy),'Quantity':picked.quantity,'Market value':money(picked.market_value),'Data status':picked.status}:view==='waiting'?{'Order ID':picked.id||'Awaiting report','Submitted':stamp(picked.created_at),'Status':picked.status,'Data status':picked.dataStatus,'Limit price':money(picked.limit)}:{'Execution ID':picked.id,'Order ID':picked.order_id,'Order status':picked.status,'Fee':picked.fee==null?'Pending':money(picked.fee),'Executed':stamp(picked.time)}):[];
    const history=(strategy==='all'?combined().history:forwardState[strategy]?.history||[]).filter(p=>!start(period)||new Date(p.time)>=start(period));
    // The existing chart renderer uses real observations; an empty period stays empty.
    window.dashboardHistory=history;
    return `<div class="dash-shell">
      <div class="dash-heading"><div><span class="dash-eyebrow">PAPER TRADING</span><h2>Portfolio overview</h2></div><div class="dash-global">${dropdown('Strategy filter','strategy',[['all','All strategies'],['etf','ETF rotation'],['crypto','BTC / ETH']],strategy)}${dropdown('Time frame','period',Object.entries(labels),period)}</div></div>
      <div class="dash-kpis">${metric('Current equity',money(sum('equity')))}${metric('Allocated cash',money(sum('cash')))}${metric('Unrealised P&L',money(sum('unrealised')))}${metric(labels[period]+' · confirmed fills',activity?.started?activity.fills:'—')}</div>
      <div class="dash-overview"><section class="fp-card dash-chart-card"><div class="dash-toolbar"><h2>Equity performance</h2><span class="fp-muted">${labels[period]} · USD</span></div><div class="fp-chart"><canvas id="chart-dashboard" aria-label="Forward equity compared with buy and hold"></canvas></div><p class="fp-muted">Observed forward results · up to 500 recent samples · UTC</p></section>
      <section class="fp-card dash-health"><div class="dash-toolbar"><h2>Account status</h2><span class="dash-dot ${valid?'ready':''}"></span></div>${states.map(({id,s})=>`<div class="dash-account"><strong>${name(id)}</strong><span>${esc(fresh(s)?s?.connection||'Unverified':'Awaiting service / stale')}</span><small>${esc(s?.account||'Account not configured')} · ${esc(stamp(s?.updated_at))}</small></div>`).join('')}<div class="dash-small-stats"><span>Realised P&L <b>${money(sum('realised'))}</b></span><span>Reported costs <b>${money(sum('costs'))}</b></span></div><p class="fp-muted">Current strategy allocations; unallocated broker cash excluded.</p></section></div>
      ${forwardState.error||states.some(({s})=>s?.error)||!valid?`<div class="dash-notice" role="status">${esc(forwardState.error||states.find(({s})=>s?.error)?.s.error||'Awaiting fresh, reconciled valuations. Current KPIs are unavailable; older records are labelled stale.')}</div>`:''}
      <section class="fp-card dash-details"><div class="dash-tabs" role="tablist" aria-label="Trading details">${[['positions','Active trades'],['waiting','Waiting orders'],['fills','Filled orders']].map(([key,label])=>`<button role="tab" id="tab-${key}" aria-controls="dash-panel" aria-selected="${key===view}" onclick="Dashboard.filter('view','${key}')">${label}<span>${key==='positions'?positions.length:key==='waiting'?orders.length:activity?.started?activity.fills:'—'}</span></button>`).join('')}</div>
      <div class="dash-detail-filters">${dropdown('Asset','symbol',options('symbol'),symbol)}${view!=='positions'?dropdown('Side','side',[['all','All sides'],['buy','Buy'],['sell','Sell']],side):''}${dropdown('Status','status',options('status'),status)}<p class="fp-muted">${view==='fills'?`${labels[period]} · ${rows.length} archive records loaded`: 'Current snapshot · not date-filtered'}</p>${view==='fills'?`<button class="dash-refresh" onclick="Dashboard.load()" ${loading||!experiment?'disabled':''}>Refresh fills</button>`:''}</div>
      <div id="dash-panel" role="tabpanel" aria-labelledby="tab-${view}"><div class="fp-table-wrap"><table class="fp-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}<th>Details</th></tr></thead><tbody>${visible.length?visible.map((r,i)=>`<tr class="${selected===page*5+i?'dash-selected':''}">${values(r).map(v=>`<td>${esc(v)}</td>`).join('')}<td><button class="dash-row-button" aria-expanded="${selected===page*5+i}" onclick="Dashboard.detail(${page*5+i})">${selected===page*5+i?'Close':'View'}</button></td></tr>`).join(''):`<tr><td colspan="6" class="dash-empty">${view==='fills'&&loading?'Loading confirmed fills…':view==='fills'&&!summary?.archive_ready?'Awaiting service fill archive':source.length?'No records match these filters': 'No '+(view==='positions'?'verified positions':view==='waiting'?'reported waiting orders':'confirmed fills')+' to display'}</td></tr>`}</tbody></table></div>
      ${picked?`<div class="dash-record" aria-label="Selected record details">${fields.map(([k,v])=>`<div><small>${esc(k)}</small><strong>${esc(v)}</strong></div>`).join('')}</div>`:''}
      <div class="dash-footer"><span>${records.length?`${page*5+1}–${Math.min(page*5+5,records.length)} of ${records.length}`:'0 records'}${view==='fills'?' matching loaded fills':''}</span><div><button onclick="Dashboard.turn(-1)" ${page===0?'disabled':''}>Previous</button><button onclick="Dashboard.turn(1)" ${(page+1)*5>=records.length?'disabled':''}>Next</button>${view==='fills'&&more?`<button onclick="Dashboard.load(true)" ${loading?'disabled':''}>Load more fills</button>`:''}</div></div></div>
      <p class="fp-muted dash-footnote">${view==='fills'?`Partial executions are individual fills. Archive read ${esc(stamp(loadedAt))}. ${more?'Load more to include older matching records.':''} ${summary&&!fresh(summary)?'Activity totals are stale.':''}`:view==='waiting'?'Includes partial and uncertain orders. Pause does not cancel outstanding orders.':'Broker-reconciled strategy positions. Select View to inspect one record.'} ${error?esc(error):''}</p></section>
      <p class="fp-muted dash-bottom">${esc(experiment||'No forward experiment connected')} · Date filters use UTC; weeks start Monday. Asset, side and status filters apply to the detail panel only.</p></div>`;
  }
  return {render,reset,load,select,selectStrategy,start,waiting,onReport,filter,turn,detail};
})();
if(typeof module!=='undefined')module.exports=Dashboard;
