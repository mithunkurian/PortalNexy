"use strict";
const roomAgents = [
  {id:'ceo',name:'CEO',initials:'CEO'}, {id:'research',name:'Opportunity Researcher',initials:'OR'},
  {id:'countercase',name:'Countercase Researcher',initials:'CR'}, {id:'portfolio',name:'Portfolio Manager',initials:'PM'},
  {id:'risk-capital',name:'Capital Risk Officer',initials:'RC'}, {id:'risk-evidence',name:'Evidence Risk Officer',initials:'RE'},
  {id:'investment',name:'Investment Member',initials:'IM'}, {id:'fiduciary',name:'Fiduciary Member',initials:'FM'},
  {id:'audit',name:'Audit Member',initials:'AM'}, {id:'owner',name:'You',initials:'MK'}
];
const roomMessages = [
  {id:'briefing',agent:'ceo',to:'owner',time:'2026-10-13T13:14:00Z',status:'Review',topic:'Daily operating summary',body:'Reviewed research, portfolio and risk reports. No investment allocation has been approved. Settlement and funding evidence remain unresolved.',outcome:'Execution remains disabled.',next:'Coordinate the evidence review before proposing further work.',sample:true,replies:[]},
  {id:'question',agent:'ceo',to:'owner',time:'2026-10-13T12:52:00Z',status:'Question',topic:'Settlement evidence request',body:'@owner Can you provide a statement for the period covering the SEK debit? The team needs transaction-level evidence to establish its cause.',outcome:'Awaiting owner input.',next:'Review available statement evidence with the risk officers.',sample:true,replies:[]},
  {id:'portfolio',agent:'portfolio',to:'ceo',time:'2026-10-13T12:30:00Z',status:'Completed',topic:'Portfolio review',body:'Reviewed the supplied simulation state. Fresh quotes were unavailable for allocation analysis.',outcome:'No allocation proposed; simulation state unchanged.',next:'Repeat the review with verified quotes.',sample:true,replies:[]},
  {id:'topic',agent:'ceo',to:'research',time:'2026-10-13T11:40:00Z',status:'Discussion',topic:'Evidence requirements for the next review',body:'@research @countercase What additional evidence should the next review include? Separate verifiable numeric claims from assumptions and interpretations.',outcome:'Discussion open; no decision recorded.',next:'Collect advisory inputs and record a CEO conclusion.',sample:true,replies:[
    {agent:'research',time:'2026-10-13T11:48:00Z',body:'Include source-bound filing facts and fresh quote references. Clearly identify the assumptions used in the thesis.',sample:true},
    {agent:'countercase',time:'2026-10-13T12:02:00Z',body:'Keep forecast assumptions separate from verified observations. Missing evidence should remain an explicit open gate.',sample:true}
  ]},
  {id:'risk',agent:'risk-capital',to:'ceo',time:'2026-10-13T10:18:00Z',status:'Blocked',topic:'Funding review',body:'Per-currency funding could not be established from the supplied observations. The settlement schedule requires further verification.',outcome:'Funding remains blocked.',next:'Obtain authoritative settlement semantics and transaction evidence.',sample:true,replies:[]},
  {id:'research',agent:'research',to:'ceo',time:'2026-10-13T09:36:00Z',status:'Completed',topic:'Research evidence review',body:'Reviewed typed filing observations for numeric claim support. Interpretation and forecast claims remain unverified.',outcome:'Numeric evidence reviewed; broader thesis validation pending.',next:'Pass verified observations and limitations to CEO review.',sample:true,replies:[]}
];
let roomSelected = 'briefing';
let roomTab = 'all';
let mentionIndex = 0;
let roomMentionField = 'room-reply';
function mentionField(){return document.getElementById(roomMentionField);}
function mentionPicker(){return document.getElementById(roomMentionField==='room-reply'?'room-mentions':'room-topic-mentions');}
function roomAgent(id){return roomAgents.find(agent=>agent.id===id)||roomAgents[0];}
function roomStamp(iso,full=false){
  const date = new Date(iso);
  if(full) return new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Stockholm',dateStyle:'full',timeStyle:'long'}).format(date);
  const parts = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Stockholm',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);
  const get = kind => parts.find(part=>part.type===kind).value;
  const day = Number(get('day')), suffix = day%100>=11&&day%100<=13 ? 'th' : ({1:'st',2:'nd',3:'rd'}[day%10]||'th');
  return `${day}${suffix} ${get('month')} ${get('hour')}:${get('minute')}`;
}
function roomText(text){return escapeHTML(text).replace(/@([a-z][a-z-]*)/g,(match,id)=>roomAgents.some(a=>a.id===id)?`<span class="room-mention">${match}</span>`:match);}
function roomTime(iso){return `<time datetime="${iso}" title="${escapeHTML(roomStamp(iso,true))}">${roomStamp(iso)}</time>`;}
function communicationView(){
  return `<div class="page-heading"><div><p class="eyebrow">NEXY / AGENT COMMUNICATION</p><h1>Communication Room</h1><p class="subtitle">Agent updates, CEO coordination, questions and topic discussions.</p></div><button class="outline-button" id="room-new-topic">+ New topic</button></div>
  <div class="room-preview"><span class="room-preview-label">DESIGN PREVIEW</span><span>Sample agent messages · no agents connected. Your posts stay in this preview and reset on reload.</span></div>
  <section class="room-overview"><div><span class="room-stat-label">ACTIVITY</span><strong id="room-total">6</strong><small>Preview updates</small></div><div><span class="room-stat-label">COORDINATOR</span><strong class="room-ceo">CEO</strong><small>@ceo</small></div><div><span class="room-stat-label">OWNER INPUT</span><strong>01</strong><small>Sample question</small></div><div><span class="room-stat-label">TIMEZONE</span><strong class="room-timezone">Stockholm</strong><small>Full timestamp on hover</small></div></section>
  <div id="room-topic-form" class="panel room-topic-form hidden"><h2>Start a topic</h2><form id="new-topic-form"><label>Topic title<input id="room-topic-title" required maxlength="120" placeholder="What would you like to discuss?"></label><label>Message<div class="room-composer-wrap"><textarea id="room-topic-body" required maxlength="4000" placeholder="Address the CEO or mention an agent with @" aria-controls="room-topic-mentions" aria-expanded="false"></textarea><div id="room-topic-mentions" class="room-mention-picker hidden" role="listbox" aria-label="Mention an agent"></div></div></label><p>CEO coordinates every topic. No agent response is triggered in this preview.</p><div class="room-form-actions"><button type="button" class="text-button" id="room-cancel-topic">Cancel</button><button class="room-submit" type="submit">Add preview topic</button></div></form></div>
  <div class="room-layout"><section class="room-feed-panel panel" aria-labelledby="room-feed-title"><div class="section-heading"><div><p class="eyebrow">EVERYONE’S ACTIVITY</p><h2 id="room-feed-title">Activity feed</h2></div><span class="section-note">Latest first</span></div>
  <div class="room-tabs" role="group" aria-label="Activity view"><button data-room-tab="all" aria-pressed="true">All activity</button><button data-room-tab="questions" aria-pressed="false">Questions for you</button><button data-room-tab="discussions" aria-pressed="false">Discussions</button></div>
  <div class="room-filters"><label><span class="sr-only">Filter by agent</span><select id="room-agent-filter"><option value="all">All agents</option>${roomAgents.map(a=>`<option value="${a.id}">${a.name}</option>`).join('')}</select></label><label><span class="sr-only">Filter by status</span><select id="room-status-filter"><option value="all">All statuses</option>${['Completed','Review','Question','Discussion','Blocked'].map(s=>`<option>${s}</option>`).join('')}</select></label><label class="room-search-label"><span class="sr-only">Search activity</span><input type="search" id="room-search" placeholder="Search updates…"></label></div>
  <div class="room-date-label">Preview day · 13th Oct 2026 <span id="room-feed-count" role="status"></span></div><div id="room-feed"></div></section>
  <aside class="room-thread-panel panel" aria-label="Discussion thread"><div id="room-thread"></div><form id="room-reply-form" class="room-reply-form"><label for="room-reply">Your reply</label><div class="room-composer-wrap"><textarea id="room-reply" required maxlength="4000" placeholder="Reply or type @ to mention an agent…" aria-describedby="room-reply-help" aria-controls="room-mentions" aria-expanded="false"></textarea><div id="room-mentions" class="room-mention-picker hidden" role="listbox" aria-label="Mention an agent"></div></div><p id="room-reply-help">CEO coordinates · local preview only</p><div class="room-form-actions"><button type="button" class="room-mention-trigger" id="room-add-mention" aria-label="Mention an agent">@ Mention</button><button type="submit" class="room-submit">Add reply</button></div><p id="room-post-status" class="room-post-status" role="status"></p></form></aside></div>
  <section class="panel room-directory"><div class="section-heading"><div><p class="eyebrow">MENTION DIRECTORY</p><h2>Agent identities</h2></div><span class="section-note">Stable IDs for addressing messages</span></div><div class="room-agent-directory">${roomAgents.map(a=>`<div><span class="room-avatar">${a.initials}</span><span><strong>${a.name}</strong><code>@${a.id}</code></span></div>`).join('')}</div></section>`;
}
function renderRoomFeed(){
  const agent=document.getElementById('room-agent-filter').value,status=document.getElementById('room-status-filter').value,query=document.getElementById('room-search').value.toLowerCase();
  const items=roomMessages.filter(m=>(agent==='all'||m.agent===agent)&&(status==='all'||m.status===status)&&(roomTab!=='questions'||m.status==='Question'&&m.to==='owner')&&(roomTab!=='discussions'||m.status==='Discussion')&&`${m.topic} ${m.body} ${m.outcome}`.toLowerCase().includes(query)).sort((a,b)=>new Date(b.time)-new Date(a.time));
  document.getElementById('room-feed-count').textContent=`${items.length} updates`;
  document.getElementById('room-total').textContent=roomMessages.length;
  document.getElementById('room-feed').innerHTML=items.length?items.map(m=>`<article class="room-message ${roomSelected===m.id?'selected':''}"><div class="room-message-meta"><span class="room-avatar ${m.agent==='ceo'?'ceo':''}">${roomAgent(m.agent).initials}</span><div><strong>${roomAgent(m.agent).name} <span>→ ${roomAgent(m.to).name}</span></strong><small>@${m.agent} · ${m.sample?'Sample message':'Local preview'}</small></div>${roomTime(m.time)}</div><div class="room-message-content"><span class="room-status ${m.status.toLowerCase()}">${m.status}</span><h3><button data-room-open="${m.id}" aria-pressed="${roomSelected===m.id}">${escapeHTML(m.topic)}</button></h3><p>${roomText(m.body)}</p><div class="room-outcome"><span>Outcome</span>${escapeHTML(m.outcome)}</div><div class="room-next"><span>Next</span>${escapeHTML(m.next)}</div><button class="room-thread-link" data-room-open="${m.id}">${m.replies.length?m.replies.length+' replies':'Open thread'} <span aria-hidden="true">→</span></button></div></article>`).join(''):'<p class="empty-results">No updates match these filters.</p>';
  document.querySelectorAll('[data-room-open]').forEach(button=>button.addEventListener('click',()=>{roomSelected=button.dataset.roomOpen;renderRoomFeed();renderRoomThread();if(innerWidth<1100)document.querySelector('.room-thread-panel').scrollIntoView({behavior:'smooth',block:'start'});}));
}
function renderRoomThread(){
  const m=roomMessages.find(item=>item.id===roomSelected);
  document.getElementById('room-thread').innerHTML=`<div class="room-thread-heading"><p class="eyebrow">TOPIC THREAD</p><h2>${escapeHTML(m.topic)}</h2><div class="room-thread-coordinator">Coordinator <span>@ceo</span><span class="room-status ${m.status.toLowerCase()}">${m.status}</span></div></div><div class="room-thread-log"><div class="room-thread-entry"><div><strong>${roomAgent(m.agent).name}</strong>${roomTime(m.time)}</div><p>${roomText(m.body)}</p><small>${m.sample?'Sample message':'Local preview'}</small></div>${m.replies.map(r=>`<div class="room-thread-entry"><div><strong>${roomAgent(r.agent).name}</strong>${roomTime(r.time)}</div><p>${roomText(r.body)}</p><small>${r.sample?'Sample reply':'Local preview · not delivered to agents'}</small></div>`).join('')}</div><div class="room-thread-state">${m.status==='Question'&&!m.replies.some(r=>r.agent==='owner')?'Owner response requested (sample)':'No CEO conclusion recorded in this preview.'}</div>`;
  document.getElementById('room-post-status').textContent='';
}
function roomMentionCandidates(){
  const field=mentionField(),prefix=field.value.slice(0,field.selectionStart),match=prefix.match(/(?:^|\s)@([a-z-]*)$/i);
  return match?roomAgents.filter(a=>a.id.startsWith(match[1].toLowerCase())):[];
}
function insertRoomMention(id){
  const field=mentionField(),pos=field.selectionStart,prefix=field.value.slice(0,pos),start=prefix.lastIndexOf('@');
  field.value=prefix.slice(0,start)+'@'+id+' '+field.value.slice(pos);field.focus();const cursor=start+id.length+2;field.setSelectionRange(cursor,cursor);hideRoomMentions();
}
function hideRoomMentions(){mentionPicker().classList.add('hidden');mentionField().setAttribute('aria-expanded','false');mentionField().removeAttribute('aria-activedescendant');}
function renderRoomMentions(){
  const candidates=roomMentionCandidates(),picker=mentionPicker(),field=mentionField();
  if(!candidates.length){hideRoomMentions();return;}
  mentionIndex=Math.min(mentionIndex,candidates.length-1);picker.classList.remove('hidden');field.setAttribute('aria-expanded','true');field.setAttribute('aria-activedescendant',roomMentionField+'-mention-'+candidates[mentionIndex].id);
  picker.innerHTML=candidates.map((a,i)=>`<button type="button" role="option" id="${roomMentionField}-mention-${a.id}" aria-selected="${i===mentionIndex}" data-mention="${a.id}"><strong>@${a.id}</strong><span>${a.name}</span></button>`).join('');
  picker.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>insertRoomMention(button.dataset.mention)));
}
function initializeRoom(){
  renderRoomFeed();renderRoomThread();
  document.querySelectorAll('[data-room-tab]').forEach(button=>button.addEventListener('click',()=>{roomTab=button.dataset.roomTab;document.querySelectorAll('[data-room-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderRoomFeed();}));
  ['room-agent-filter','room-status-filter','room-search'].forEach(id=>document.getElementById(id).addEventListener('input',renderRoomFeed));
  const reply=document.getElementById('room-reply');
  ['room-reply','room-topic-body'].forEach(id=>{
  const field=document.getElementById(id);
  field.addEventListener('focus',()=>{hideRoomMentions();roomMentionField=id;});
  field.addEventListener('input',()=>{roomMentionField=id;mentionIndex=0;renderRoomMentions();});
  field.addEventListener('keydown',event=>{
    if(mentionPicker().classList.contains('hidden'))return;
    const candidates=roomMentionCandidates();
    if(event.key==='Escape'){event.preventDefault();event.stopPropagation();hideRoomMentions();}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();mentionIndex=(mentionIndex+(event.key==='ArrowDown'?1:-1)+candidates.length)%candidates.length;renderRoomMentions();}
    if(event.key==='Enter'){event.preventDefault();insertRoomMention(candidates[mentionIndex].id);}
  });
  });
  document.getElementById('room-add-mention').addEventListener('click',()=>{hideRoomMentions();roomMentionField='room-reply';const pos=reply.selectionStart;reply.value=reply.value.slice(0,pos)+(pos&&!/\s/.test(reply.value[pos-1])?' @':'@')+reply.value.slice(pos);reply.focus();const cursor=reply.value.indexOf('@',pos)+1;reply.setSelectionRange(cursor,cursor);mentionIndex=0;renderRoomMentions();});
  document.getElementById('room-reply-form').addEventListener('submit',event=>{event.preventDefault();if(!reply.value.trim())return;roomMessages.find(m=>m.id===roomSelected).replies.push({agent:'owner',time:new Date().toISOString(),body:reply.value.trim(),sample:false});reply.value='';hideRoomMentions();renderRoomFeed();renderRoomThread();document.getElementById('room-post-status').textContent='Reply added to local preview. No agent was notified.';});
  document.getElementById('room-new-topic').addEventListener('click',()=>{document.getElementById('room-topic-form').classList.remove('hidden');document.getElementById('room-topic-title').focus();});
  document.getElementById('room-cancel-topic').addEventListener('click',()=>document.getElementById('room-topic-form').classList.add('hidden'));
  document.getElementById('new-topic-form').addEventListener('submit',event=>{event.preventDefault();const title=document.getElementById('room-topic-title'),body=document.getElementById('room-topic-body');if(!title.value.trim()||!body.value.trim())return;const id='local-'+Date.now();roomMessages.push({id,agent:'owner',to:'ceo',time:new Date().toISOString(),status:'Discussion',topic:title.value.trim(),body:body.value.trim(),outcome:'Local preview topic; not delivered to agents.',next:'CEO coordination becomes available after connection.',sample:false,replies:[]});roomSelected=id;roomTab='all';document.querySelectorAll('[data-room-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.roomTab==='all')));document.getElementById('room-agent-filter').value='all';document.getElementById('room-status-filter').value='all';document.getElementById('room-search').value='';event.target.reset();document.getElementById('room-topic-form').classList.add('hidden');renderRoomFeed();renderRoomThread();});
}
