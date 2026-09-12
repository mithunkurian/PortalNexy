'use strict';
// Read-only view: broker actions remain exclusively in Paper Trading.
const Dashboard=(()=>{
  const labels={today:'Today',week:'This week',month:'This month',days30:'Last 30 days',all:'All time'};
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
  function reset(value){experiment=value;generation++;rows=[];cursor=null;more=false;loading=false;error='';loadedAt=null;fillCount=null;}
  function onReport(report){
    const next=report?.periods?.all?.all?.fills;
    if(next!=null&&next!==fillCount){fillCount=next;generation++;loading=false;loadedAt=null;rows=[];cursor=null;more=false;error='';}
  }
  async function load(append=false){
    if(!experiment||loading)return;
    const token=++generation;loading=true;error='';
    if(!append){rows=[];cursor=null;more=false;}renderForward();
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
  function select(key){if(!labels[key])return;period=key;generation++;loading=false;load();renderForward();}
  function selectStrategy(value){if(!['all','etf','crypto'].includes(value))return;strategy=value;renderForward();}
  function render(){
    if(experiment!==forwardState.experiment)reset(forwardState.experiment);
    if(experiment&&!loadedAt&&!loading&&!error)queueMicrotask(()=>load());
    const ids=strategy==='all'?['etf','crypto']:[strategy];
    const states=ids.map(id=>({id,s:forwardState[id]}));
    const positions=states.flatMap(({id,s})=>(s?.portfolio?.positions||[]).map(p=>[name(id),p.symbol,p.quantity,money(p.market_value),fresh(s)&&!s.valuation_stale?'Reconciled snapshot':'Last known / stale']));
    const orders=states.flatMap(({id,s})=>(s?.orders||[]).filter(waiting).map(o=>[name(id),o.symbol+' / '+o.side,o.quantity,o.filled??'Unconfirmed',o.status,stamp(o.created_at),fresh(s)?'Service reporting':'Last known / stale']));
    const valid=states.every(({s})=>s?.inception&&fresh(s)&&!s.valuation_stale&&s.portfolio);
    const sum=k=>valid?states.reduce((a,{s})=>a+s.portfolio[k],0):null;
    const summary=forwardState.dashboard;
    const sameDay=summary?.updated_at&&new Date(summary.updated_at).toISOString().slice(0,10)===new Date().toISOString().slice(0,10);
    const activity=sameDay?summary?.periods?.[period]?.[strategy]:null;
    const count=k=>activity?.started?activity[k]:'—';
    const visible=rows.filter(f=>(strategy==='all'||f.strategy===strategy)&&forwardState[f.strategy]?.inception&&new Date(f.time)>=new Date(forwardState[f.strategy].inception)&&new Date(f.time)<=new Date());
    return `<div class="fp-banner"><div><strong>Trading overview</strong><p>${esc(experiment||'Awaiting the first forward experiment')} · Paper accounts · USD</p></div><span class="fp-tag" style="color:#182053">Forward results only</span></div>
      ${forwardState.error?`<p class="fp-error" role="alert">${esc(forwardState.error)}</p>`:''}
      <section class="fp-card"><div class="dash-toolbar"><div class="dash-periods" role="group" aria-label="Activity time frame">${Object.entries(labels).map(([key,label])=>`<button onclick="Dashboard.select('${key}')" aria-pressed="${period===key}">${label}</button>`).join('')}</div><label class="fp-muted">Strategy <select aria-label="Strategy filter" onchange="Dashboard.selectStrategy(this.value)">${[['all','All strategies'],['etf','ETF rotation'],['crypto','BTC / ETH']].map(([id,label])=>`<option value="${id}" ${strategy===id?'selected':''}>${label}</option>`).join('')}</select></label></div><p class="fp-muted">Activity uses UTC calendar dates; weeks start Monday. Current holdings and waiting orders stay visible for every time frame.</p></section>
      <section class="fp-card"><h2>Current portfolio</h2><p class="fp-muted">Strategy allocations within broker accounts. These totals are current, not filtered by date. Unallocated broker cash is excluded.</p><div class="fp-metrics">${metric('Equity',money(sum('equity')))}${metric('Allocated cash',money(sum('cash')))}${metric('Unrealised P&L',money(sum('unrealised')))}${metric('Realised P&L since inception',money(sum('realised')))}</div>
      ${states.map(({id,s})=>`<div class="dash-status"><strong>${name(id)}</strong><span>${esc(s?.account||'Account not configured')} · ${esc(fresh(s)?s?.connection||'Unverified':'Awaiting service / stale')}</span><span>Updated ${esc(stamp(s?.updated_at))}</span></div>${s?.error?`<p class="fp-error">${esc(s.error)}</p>`:''}`).join('')}
      ${!valid?'<p class="fp-error">Current totals require fresh, reconciled valuations for every selected strategy. Last known positions and orders are labelled below.</p>':''}</section>
      <section class="fp-card"><h2>${labels[period]} · execution activity</h2><p class="fp-muted">Full experiment ledger totals as of ${esc(stamp(summary?.updated_at))}. Executed value is trade turnover, not profit. Partial executions count as individual fills.</p>${summary&&!fresh(summary)?'<p class="fp-error">Activity totals are stale; refresh after the service reconnects.</p>':''}<div class="fp-metrics">${metric('Confirmed fills',count('fills'))}${metric('Orders with fills',count('orders_with_fills'))}${metric('Order submission attempts',count('orders_submitted'))}${metric('Executed value',money(activity?.started?activity.executed_value:null))}</div></section>
      <section class="fp-card"><h2>Active trades · positions</h2>${table(['Strategy','Symbol','Quantity','Market value','Data status'],positions,valid?'No open experiment positions':'No verified current positions available')}</section>
      <section class="fp-card"><h2>Waiting orders</h2><p class="fp-muted">Includes partial fills and uncertain submissions. Pausing a strategy does not cancel outstanding orders.</p>${table(['Strategy','Symbol / side','Ordered','Filled','Order status','Submitted (UTC)','Data status'],orders,states.every(({s})=>fresh(s))?'No waiting experiment orders':'Waiting-order status unavailable until the service reports')}</section>
      <section class="fp-card"><div class="dash-toolbar"><h2>Filled orders · executions</h2><button class="fp-button" onclick="Dashboard.load()" ${loading||!experiment?'disabled':''}>Refresh fills</button></div><p class="fp-muted">Confirmed broker executions only, including partial fills. Showing ${visible.length} matching fills from ${rows.length} loaded records across both strategies. ${more?'Load more to search older records in this period.':''} Archive read: ${esc(stamp(loadedAt))}.</p>
      ${error?`<p class="fp-error" role="alert">${esc(error)}</p>`:''}
      ${table(['Filled (UTC)','Strategy','Symbol / side','Quantity','Price','Fee','Order status'],visible.map(f=>[stamp(f.time),name(f.strategy),f.symbol+' / '+f.side,f.quantity,money(f.price),f.fee==null?'Pending':money(f.fee),f.order_status||'Unknown']),loading?'Loading confirmed fills…':!summary?.archive_ready?'Awaiting service fill archive':more?'No matching fills in loaded records; load more':'No confirmed fills in this period')}
      ${more?`<div class="fp-actions"><button onclick="Dashboard.load(true)" ${loading?'disabled':''}>${loading?'Loading…':'Load more fills'}</button></div>`:''}</section>`;
  }
  return {render,reset,load,select,selectStrategy,start,waiting,onReport};
})();
if(typeof module!=='undefined')module.exports=Dashboard;
