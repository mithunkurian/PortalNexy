let activeTodoPhase = 'P1';
const ROADMAP = [
  { id:'P1', phase:'Phase 1', title:'Foundation & Paper Trading',    status:'current',  badge:'Active', months:'Jan–Apr 2026',
    desc:'Infrastructure, portal, IBKR paper trading, backtesting framework.',
    tasks:['IBKR paper account live','Portal connected to Firestore','Base strategy coded & back-tested','Risk framework rules defined','Decision log operational'] },
  { id:'P2', phase:'Phase 2', title:'Strategy Refinement',           status:'upcoming', badge:null, months:'May–Aug 2026',
    desc:'Walk-forward optimisation, drawdown analysis, live paper validation.',
    tasks:['Walk-forward backtests completed','Sharpe > 1.5 confirmed','Max drawdown < 15% verified','3-month paper record clean'] },
  { id:'P3', phase:'Phase 3', title:'Live Trading — Small Size',     status:'upcoming', badge:null, months:'Sep 2026–Feb 2027',
    desc:'Go live with minimal capital, real fills, real slippage.',
    tasks:['€5k live account funded','First 10 live trades executed','Slippage vs backtest analysed','Monthly review process set'] },
  { id:'P4', phase:'Phase 4', title:'Scale & Optimise',             status:'upcoming', badge:null, months:'Mar–Dec 2027',
    desc:'Increase position size, add second strategy, NEX agent online.',
    tasks:['Account scaled to €20k','Second strategy live','NEX AI agent integrated','Automated reporting active'] },
  { id:'P5', phase:'Phase 5', title:'Fully Systematic Operations',  status:'upcoming', badge:null, months:'2028+',
    desc:'Full automation, multi-strategy, institutional-grade risk management.',
    tasks:['Portfolio fully automated','Multi-strategy live','Full audit trail in place','Annual performance report'] },
];

function renderRoadmap() {
  const el = document.getElementById('roadmap-timeline');
  if (!el) return;
  el.innerHTML = ROADMAP.map((p, i) => {
    const isCurrent = p.status === 'current';
    const borderColor = isCurrent ? 'border-primary' : 'border-outline-variant/30';
    const dotColor    = isCurrent ? 'bg-primary' : 'bg-outline-variant';
    return `
    <div class="flex gap-6 group">
      <div class="flex flex-col items-center">
        <div class="w-4 h-4 rounded-full ${dotColor} mt-1 flex-shrink-0 ring-4 ring-white"></div>
        ${i < ROADMAP.length-1 ? '<div class="w-px flex-1 bg-outline-variant/30 mt-1 mb-0"></div>' : ''}
      </div>
      <div class="pb-10 flex-1">
        <div class="surface-card rounded-2xl p-6 border ${borderColor}">
          <div class="flex flex-wrap items-center gap-2 mb-1">
            <span class="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">${p.phase} · ${p.months}</span>
            ${isCurrent ? '<span class="px-2 py-0.5 rounded-full bg-primary text-on-primary text-[10px] font-bold">Active</span>' : ''}
          </div>
          <h3 class="text-[18px] font-headline font-extrabold text-primary mb-2">${p.title}</h3>
          <p class="text-[13px] text-on-surface-variant mb-4">${p.desc}</p>
          <div id="roadmap-progress-${p.id}" class="mb-4"></div>
          <ul class="space-y-1.5">
            ${p.tasks.map(t => `<li class="flex items-center gap-2 text-[12px] text-on-surface-variant">
              <span class="material-symbols-outlined text-[14px] text-on-surface-variant/40">radio_button_unchecked</span>${t}
            </li>`).join('')}
          </ul>
        </div>
      </div>
    </div>`;
  }).join('');
  updateRoadmapProgress();
}

function updateRoadmapProgress() {
  // Will be populated from todo completion data
  ROADMAP.forEach(p => {
    const el = document.getElementById('roadmap-progress-' + p.id);
    if (!el) return;
    // Placeholder — real data comes from Firestore todos listener
    el.innerHTML = '';
  });
}

// ═══════════════════════ ACTION PLAN (TODOS) ═══════════════════════
let todos = [];

function switchTodoPhase(phase) {
  activeTodoPhase = phase;
  document.querySelectorAll('.todo-phase-btn').forEach(btn => {
    if (btn.dataset.phase === phase) {
      btn.classList.add('bg-primary','text-on-primary');
      btn.classList.remove('bg-surface-container','text-on-surface-variant');
    } else {
      btn.classList.remove('bg-primary','text-on-primary');
      btn.classList.add('bg-surface-container','text-on-surface-variant');
    }
  });
  renderTodos();
}

function renderTodos() {
  const phaseTodos = todos.filter(t => t.phase === activeTodoPhase);
  const done = phaseTodos.filter(t => t.status === 'done').length;
  const total = phaseTodos.length;
  const pct = total ? Math.round((done/total)*100) : 0;

  const progressEl = document.getElementById('todo-progress-fill');
  const progressLbl = document.getElementById('todo-progress-label');
  if (progressEl) { progressEl.dataset.target = pct; animateProgressBars(); }
  if (progressLbl) progressLbl.textContent = `${done}/${total} tasks · ${pct}%`;

  const list = document.getElementById('todo-list');
  if (!list) return;
  const sorted = [...phaseTodos].sort((a,b) => (a.order||0)-(b.order||0));
  if (!sorted.length) {
    list.innerHTML = '<div class="text-center py-10 text-on-surface-variant/50 text-[13px]">No tasks for this phase.</div>';
    return;
  }
  list.innerHTML = sorted.map(t => `
    <div class="todo-item ${t.status==='done'?'done':''} flex items-center gap-4 py-3.5 border-b border-outline-variant/10 last:border-0 cursor-pointer" onclick="toggleTodo('${t.id}')">
      <div class="w-5 h-5 rounded-full border-2 ${t.status==='done'?'border-primary bg-primary':'border-outline-variant'} flex-shrink-0 flex items-center justify-center">
        ${t.status==='done'?'<span class="material-symbols-outlined text-[12px] text-on-primary">check</span>':''}
      </div>
      <span class="todo-title flex-1 text-[13px] text-on-surface">${esc(t.title)}</span>
    </div>
  `).join('');
}

async function toggleTodo(id) {
  const todo = todos.find(t => t.id === id);
  if (!todo) return;
  const newStatus = todo.status === 'done' ? 'pending' : 'done';
  await db.collection('todos').doc(id).update({ status: newStatus });
}

async function addTodo() {
  const input = document.getElementById('todo-input');
  if (!input) return;
  const title = input.value.trim();
  if (!title) return;
  input.value = '';
  const phaseTodos = todos.filter(t => t.phase === activeTodoPhase);
  const order = phaseTodos.length ? Math.max(...phaseTodos.map(t => t.order||0)) + 1 : 1;
  await db.collection('todos').add({
    phase: activeTodoPhase,
    title,
    status: 'pending',
    order,
    created_at: firebase.firestore.FieldValue.serverTimestamp(),
  });
}

// ═══════════════════════ DESIGN DOC SCROLL SPY ═══════════════════════
function scrollToPlan(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior:'smooth' });
}

function planScrollSpy() {
  const container = document.querySelector('#page-design .design-scroll-area');
  const sections   = document.querySelectorAll('#page-design .plan-section');
  if (!container || !sections.length) return;
  container.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(s => {
      if (s.offsetTop <= container.scrollTop + 80) current = s.id;
    });
    document.querySelectorAll('.plan-toc-item').forEach(item => {
      item.classList.toggle('active', item.dataset.target === current);
    });
  });
}

// ═══════════════════════ NEX CHAT ═══════════════════════
const NEX_AGENT = {
  id: 'nex',
  name: 'NEX',
  role: 'System Intelligence · NexyCapitals',
  icon: 'psychology',
};

let activeChatAgentId = null;
let chatUnsubscribe   = null;

function openNEXChat() { openChat('nex'); }

function openChat(agentId) {
  const agent = agentId === 'nex' ? NEX_AGENT : { id:agentId, name:agentId.toUpperCase(), role:'Agent', icon:'smart_toy' };
  activeChatAgentId = agentId;

  const iconWrap = document.getElementById('chat-agent-icon');
  iconWrap.className = 'w-11 h-11 bg-primary/10 rounded-xl flex items-center justify-center';
  iconWrap.innerHTML = `<span class="material-symbols-outlined text-[22px] text-primary">${agent.icon}</span>`;
  document.getElementById('chat-agent-name').textContent = agent.name;
  document.getElementById('chat-agent-role').textContent = agent.role;

  document.getElementById('chat-panel').classList.remove('translate-x-full');
  document.getElementById('chat-backdrop').classList.remove('hidden');

  if (chatUnsubscribe) chatUnsubscribe();
  chatUnsubscribe = db.collection('chats').doc(agentId)
    .collection('messages')
    .orderBy('timestamp', 'asc')
    .onSnapshot(snap => {
      const msgs = snap.docs.map(d => ({ id:d.id, ...d.data() }));
      renderChatMessages(msgs, agent);
      const last = msgs[msgs.length - 1];
      const typing = document.getElementById('chat-typing');
      if (last && last.role === 'user') typing.classList.remove('hidden');
      else typing.classList.add('hidden');
    }, err => console.warn('Chat listener:', err.code));

  setTimeout(() => document.getElementById('chat-input').focus(), 300);
}

function closeChat() {
  document.getElementById('chat-panel').classList.add('translate-x-full');
  document.getElementById('chat-backdrop').classList.add('hidden');
  if (chatUnsubscribe) { chatUnsubscribe(); chatUnsubscribe = null; }
  activeChatAgentId = null;
}

function renderChatMessages(msgs, agent) {
  const c = document.getElementById('chat-messages');
  if (!msgs.length) {
    c.innerHTML = `
      <div class="flex flex-col items-center justify-center h-full text-center py-12 px-6">
        <div class="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mb-4">
          <span class="material-symbols-outlined text-[28px] text-primary">${agent.icon}</span>
        </div>
        <p class="text-[14px] font-bold text-on-surface mb-2">Chat with ${agent.name}</p>
        <p class="text-[12px] text-on-surface-variant leading-relaxed">Ask about current orders, positions, P&amp;L, strategy status or the next scheduled action.</p>
        <div class="nex-prompts">
          <button onclick="askNEX('What are the current active orders?')">Current active orders</button>
          <button onclick="askNEX('Summarize PNL this week')">This week’s P&amp;L</button>
          <button onclick="askNEX('Is anything blocked or stale?')">System health</button>
        </div>
      </div>`;
    return;
  }
  c.innerHTML = msgs.map(m => {
    const html = (m.content || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
    if (m.role === 'user') {
      return `<div class="flex justify-end">
        <div class="max-w-[82%] bg-primary text-on-primary px-4 py-3 rounded-2xl rounded-tr-sm text-[13px] leading-relaxed">${html}</div>
      </div>`;
    }
    return `<div class="flex items-end gap-2.5">
      <div class="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center bg-primary/10">
        <span class="material-symbols-outlined text-[13px] text-primary">psychology</span>
      </div>
      <div class="max-w-[82%] bg-surface-container px-4 py-3 rounded-2xl rounded-tl-sm text-[13px] text-on-surface leading-relaxed">${html}</div>
    </div>`;
  }).join('');
  c.scrollTop = c.scrollHeight;
}

function nexAsOf(states) {
  const values=states.map(s=>s?.updated_at).filter(Boolean).sort();
  return values.length?stamp(values[0]):'no verified update';
}

function nexAnswer(question) {
  const text=question.toLowerCase();
  const states=['etf','crypto'].map(id=>({id,s:forwardState[id]}));
  const names={etf:'ETF rotation',crypto:'BTC/ETH momentum'};
  const asOf=nexAsOf(states.map(x=>x.s));
  if(/order|waiting|pending|open/.test(text)) {
    const orders=states.flatMap(({id,s})=>(s?.orders||[]).filter(Dashboard.waiting).map(o=>({...o,strategy:id})));
    const stale=states.filter(({s})=>!fresh(s)).map(({id})=>names[id]);
    if(!orders.length)return stale.length?`I cannot confirm that there are no active orders because ${stale.join(' and ')} ${stale.length===1?'is':'are'} stale. Last common update: ${asOf}.`:`As of ${asOf}, there are no broker-reported active strategy orders.`;
    return `As of ${asOf}, there ${orders.length===1?'is':'are'} ${orders.length} active ${orders.length===1?'order':'orders'}:\n`+
      orders.map(o=>`• ${names[o.strategy]}: ${String(o.side||'').toUpperCase()} ${o.quantity} ${o.symbol} · ${o.filled||0} filled · ${o.status}${o.limit?` · limit ${money(o.limit)}`:''}${fresh(forwardState[o.strategy])?'':' · STALE SNAPSHOT'}`).join('\n');
  }
  if(/pnl|p&l|profit|loss|performance|return/.test(text)) {
    const key=/today/.test(text)?'today':/month/.test(text)?'month':/all/.test(text)?'all':'week';
    const label={today:'today',week:'this week',month:'this month',all:'since inception'}[key];
    const lower=Dashboard.start(key);
    const lines=[];let total=0,covered=0;
    for(const {id,s} of states){
      if(!s?.inception||!fresh(s)||s.valuation_stale||!s.portfolio){lines.push(`• ${names[id]}: unavailable — ${s?.error||'awaiting a fresh reconciled valuation'}`);continue;}
      const history=(s.history||[]).filter(p=>!lower||new Date(p.time)>=lower);
      const baseline=history[0]?.equity;
      if(baseline==null){lines.push(`• ${names[id]}: no opening observation for ${label}`);continue;}
      const change=s.portfolio.equity-baseline;total+=change;covered++;
      lines.push(`• ${names[id]}: ${money(change)} (${money(baseline)} → ${money(s.portfolio.equity)})`);
    }
    return `P&L ${label}, marked from the first available period observation, as of ${asOf}:\n${lines.join('\n')}\n${covered?`Combined across ${covered} reporting ${covered===1?'strategy':'strategies'}: ${money(total)}.`:'No reconciled period P&L is currently available.'}`;
  }
  if(/position|holding|active trade/.test(text)) {
    const positions=states.flatMap(({id,s})=>(s?.portfolio?.positions||[]).map(p=>({...p,strategy:id,valid:fresh(s)&&!s.valuation_stale})));
    if(!positions.length)return `As of ${asOf}, no attributed strategy positions are available.`;
    return `Attributed positions as of ${asOf}:\n`+positions.map(p=>`• ${names[p.strategy]}: ${p.quantity} ${p.symbol} · ${money(p.market_value)}${p.valid?'':' · STALE'}`).join('\n');
  }
  if(/next|schedule|evaluation|cycle/.test(text)) {
    return `Scheduled strategy actions as of ${asOf}:\n`+states.map(({id,s})=>`• ${names[id]}: next evaluation ${stamp(s?.next_evaluation)}; next execution ${stamp(s?.next_execution)}`).join('\n');
  }
  if(/blocked|stale|health|status|connected|connection|error/.test(text)) {
    return `System health as of ${asOf}:\n`+states.map(({id,s})=>`• ${names[id]}: ${!fresh(s)?'STALE':s?.error?'ATTENTION — '+s.error:(s?.connection||'unverified')+'; '+(s?.reconciliation||'not reconciled')}`).join('\n');
  }
  return `I can answer from PortalNexy’s verified state. Try “current active orders”, “summarize P&L this week”, “current positions”, “system health”, or “next scheduled evaluation”. Data timestamp: ${asOf}.`;
}

async function askNEX(question) {
  if(activeChatAgentId!=='nex')openNEXChat();
  const input=document.getElementById('chat-input');input.value=question;
  await sendChatMessage();
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text  = input.value.trim();
  if (!text || !activeChatAgentId) return;
  input.value = '';
  input.style.height = 'auto';
  try {
    const messages=db.collection('chats').doc(activeChatAgentId).collection('messages');
    await messages
      .add({
        role:      'user',
        content:   text,
        answered:  false,
        timestamp: firebase.firestore.FieldValue.serverTimestamp(),
      });
    if(activeChatAgentId==='nex')await messages.add({
      role:'assistant',content:nexAnswer(text),answered:true,
      source:'broker-reconciled PortalNexy state',timestamp:firebase.firestore.FieldValue.serverTimestamp(),
    });
  } catch (e) { console.error('Chat send failed:', e); }
}
