// Offline UI integration: mock Firebase only inside this browser test, never in shipped code.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const root=path.resolve(__dirname,'../public');
const mock=`
if (!window.firebase) { (()=>{
 window.__writes=[];
 const empty={exists:false,data:()=>({}),docs:[]};
 function reference(path,lower=null,offset=0,size=100){return {where:(field,op,value)=>reference(path,value,offset,size),limit:n=>reference(path,lower,offset,n),startAfter:doc=>reference(path,lower,doc.index+1,size),get:async()=>{const all=(window.__archive||[]).filter(f=>!lower||f.time>=lower);return {docs:all.slice(offset,offset+size).map((f,i)=>({data:()=>f,index:offset+i}))};},collection:n=>reference(path+'/'+n),doc:n=>reference(path+'/'+n),orderBy:()=>reference(path),
 onSnapshot:fn=>{queueMicrotask(()=>fn(path==='forward/current'&&window.__fixture?{exists:true,data:()=>({experiment:'offline-test'})}:path.endsWith('/service/dashboard')&&window.__dashboard?{exists:true,data:()=>window.__dashboard}:path.includes('/strategies/')&&window.__fixture?{exists:true,data:()=>window.__fixture[path.split('/').pop()]}:empty));return ()=>{};},
 set:async data=>{window.__writes.push({path,data});},add:async()=>{},update:async()=>{}};}
 const authObject={onAuthStateChanged:fn=>queueMicrotask(()=>fn({email:'mithunkurian@gmail.com',displayName:'UI verification'})),signOut:()=>{},signInWithPopup:async()=>{}};
 function auth(){return authObject;}auth.GoogleAuthProvider=function(){};
 function firestore(){return {collection:n=>reference(n)};}firestore.FieldValue={serverTimestamp:()=>({serverTime:true})};
 window.firebase={initializeApp:()=>{},auth,firestore};
 })();
}`;
async function run(){
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url==='/'?'index.html':req.url.split('?')[0]);if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(file));});
 await new Promise(resolve=>server.listen(8765,'127.0.0.1',resolve));
 let browser;
 try {
  browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/firebasejs/**',route=>route.fulfill({contentType:'text/javascript',body:mock}));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  assert.deepEqual(errors,[], 'Initial page JavaScript errors');
  await page.getByText('Paper Trading',{exact:true}).first().click();
  await page.locator('#forward-paper h2').first().waitFor();
  assert.equal(await page.locator('nav').getByText('Live Trading',{exact:true}).count(),0);
  assert.equal(await page.locator('nav').getByText('Backtest Lab',{exact:true}).count(),0);
  assert.equal(await page.locator('#forward-paper button:enabled').count(),0);
  assert.match(await page.locator('#forward-paper').innerText(),/No confirmed forward fills/);
  assert.equal(await page.evaluate(()=>window.__writes.length),0);
  for(const name of ['Command Centre','Dashboard','Risk Monitor','Decision Log','Finance','Boardroom','Roadmap','Action Plan','Design Doc']){
   await page.locator('nav').getByText(name,{exact:true}).click();
  }
  await page.locator('nav').getByText('Paper Trading',{exact:true}).click();
  fs.mkdirSync(path.resolve(__dirname,'../.firebase/ui-qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/paper-desktop.png'),fullPage:true,animations:'disabled'});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/paper-mobile.png'),fullPage:true,animations:'disabled'});
  // Explicitly labeled offline fixtures exercise rendering and the ONLY allowed command path.
  await page.addInitScript(()=>{
   const now=new Date().toISOString();const base={updated_at:now,inception:null,mode:'not_started',connection:'connected',account:'OFFLINE_TEST',broker:'Offline test fixture',version:'test-only',portfolio:null};
   window.__fixture={etf:{...base},crypto:{...base}};
  });
  await page.reload({waitUntil:'networkidle'});
  await page.evaluate(()=>navigate('paper'));
  await page.getByRole('button',{name:'Start experiment'}).first().click();
  const writes=await page.evaluate(()=>window.__writes);
  assert.equal(writes.length,1);assert.equal(writes[0].path,'forwardExperiments/offline-test/commands/etf');assert.equal(writes[0].data.action,'start');
  assert.equal(await page.evaluate(()=>typeof runtimeControl),'undefined');
  assert.deepEqual(errors,[]);
  await page.evaluate(()=>{
   const now=new Date().toISOString(),old='2026-01-01T00:00:00+00:00';
   for(const id of ['etf','crypto'])forwardState[id]={...forwardState[id],inception:old,history:[{time:now,equity:1000,benchmark:1000}],portfolio:{costs:0,equity:1000,cash:900,unrealised:10,realised:2,positions:[{symbol:id==='etf'?'SPY':'BTC/USD',quantity:1,market_value:100}]},orders:[{symbol:'SPY',side:'buy',quantity:2,filled:1,status:'partial',created_at:old}]};
   window.__archive=Array.from({length:121},(_,i)=>({id:String(i),strategy:'etf',time:now,symbol:'SPY',side:'buy',quantity:1,price:100,fee:1,order_status:'partial'}));
   forwardState.dashboard={updated_at:now,archive_ready:true,periods:{today:{all:{started:true,fills:121,orders_with_fills:1,orders_submitted:1,executed_value:12100}}}};
   navigate('dashboard');
  });
  assert.equal(await page.evaluate(()=>Dashboard.start('week',new Date('2027-01-01T12:00:00Z')).toISOString()),'2026-12-28T00:00:00.000Z');
  assert.equal(await page.evaluate(()=>Dashboard.start('month',new Date('2027-01-01T12:00:00Z')).toISOString()),'2027-01-01T00:00:00.000Z');
  const dashboard=page.locator('#forward-dashboard');
  assert.equal(await dashboard.locator('#chart-dashboard').count(),1);
  assert.equal(await dashboard.getByRole('tabpanel').count(),1);
  assert.equal(await dashboard.getByRole('tab',{name:/Active trades/}).getAttribute('aria-selected'),'true');
  await dashboard.getByRole('button',{name:'View',exact:true}).first().click();
  assert.equal(await dashboard.getByLabel('Selected record details').count(),1);
  await dashboard.getByRole('button',{name:'View',exact:true}).first().click();
  assert.equal(await dashboard.getByLabel('Selected record details').count(),1);
  await dashboard.getByRole('tab',{name:/Waiting orders/}).click();
  assert.match(await dashboard.innerText(),/partial/);
  await dashboard.getByLabel('Side',{exact:true}).selectOption('sell');
  assert.match(await dashboard.innerText(),/No records match/);
  await dashboard.getByLabel('Side',{exact:true}).selectOption('all');
  await dashboard.getByLabel('Asset',{exact:true}).selectOption('SPY');
  await dashboard.getByLabel('Status',{exact:true}).selectOption('partial');
  await dashboard.getByRole('tab',{name:/Filled orders/}).click();
  await dashboard.getByRole('button',{name:'Load more fills'}).waitFor();
  assert.match(await dashboard.innerText(),/of 100 matching loaded fills/);
  assert.equal(await dashboard.locator('tbody tr').count(),5);
  await dashboard.getByRole('button',{name:'Next',exact:true}).click();
  assert.match(await dashboard.innerText(),/6–10 of 100/);
  await dashboard.getByRole('button',{name:'Load more fills'}).click();
  await page.waitForFunction(()=>document.querySelector('#forward-dashboard').textContent.includes('of 121 matching loaded fills'));
  await dashboard.getByLabel('Strategy filter').selectOption('crypto');
  assert.match(await dashboard.innerText(),/0 records/);
  await dashboard.getByLabel('Strategy filter').selectOption('all');
  for(const key of ['week','month','days30','all','today']){
   await dashboard.getByLabel('Time frame',{exact:true}).selectOption(key);
   assert.equal(await dashboard.getByLabel('Time frame',{exact:true}).inputValue(),key);
  }
  await page.waitForFunction(()=>!document.querySelector('#forward-dashboard').textContent.includes('Loading confirmed'));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.evaluate(()=>{document.querySelectorAll('*').forEach(el=>{if(el.scrollTop)el.scrollTop=0;});});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/dashboard-mobile.png'),fullPage:true,animations:'disabled'});
  await page.setViewportSize({width:1440,height:1000});
  await page.evaluate(()=>{document.querySelectorAll('*').forEach(el=>{if(el.scrollTop)el.scrollTop=0;});});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/dashboard-desktop.png'),fullPage:true,animations:'disabled'});
  assert.ok(await dashboard.boundingBox().then(b=>b.height<900),'Desktop dashboard should be compact');
  await page.evaluate(()=>{forwardState.etf.updated_at='2020-01-01T00:00:00Z';renderForward();});
  await dashboard.getByRole('tab',{name:/Active trades/}).click();
  assert.match(await dashboard.innerText(),/Last known \/ stale/);
  assert.equal(await page.evaluate(()=>window.__writes.length),1,'Dashboard must not write broker commands');
  assert.deepEqual(errors,[]);
  console.log('UI PASS: desktop/mobile, empty states, management navigation, no legacy commands, allowlisted command route, no JS errors.');
 } finally {if(browser)await browser.close();server.close();}
}
run().catch(e=>{console.error(e);process.exitCode=1;});
