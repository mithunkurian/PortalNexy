const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const root=path.resolve(__dirname,'../public');
const endpoint='https://firestore.googleapis.com/**';
const mock=`window.firebase={initializeApp:()=>{},auth:Object.assign(()=>({onAuthStateChanged:fn=>{window.__authListener=fn;queueMicrotask(()=>fn(window.__user||null));},signOut:()=>{window.__authListener(null);return Promise.resolve();}}),{GoogleAuthProvider:function(){}})};`;
async function main(){
 const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+req.url.split('?')[0]);if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));});
 await new Promise(r=>server.listen(8767,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route('**/firebasejs/**',r=>r.fulfill({contentType:'text/javascript',body:mock}));
  await context.addInitScript(()=>{window.__user={uid:'synthetic-owner',email:'mithunkurian@gmail.com',emailVerified:true,displayName:'Founder',getIdTokenResult:async()=>({token:'synthetic-token',signInProvider:'google.com'})};});
  let count=0,stale=false,hostile=false;
  await context.route(endpoint,r=>{count++;assert.equal(r.request().method(),'GET');const stamp=new Date().toISOString();const data={schema:1,scope:'NASDAQ_US',currency:'USD',paper_only:true,published_at:stamp,source_at:stale?'2020-01-01T00:00:00Z':stamp,source_valid:true,execution_enabled:true,mode:'paper',phase:'idle',session_open:true,money:{strategy_capital_usd:'20000',owned_day_pnl_usd:'-1.25',owned_exposure_usd:'100',owned_open_risk_usd:'5'},limits:{capital_limit:'20000',daily_loss_limit:'200',reinvest_profits:false,configured_limits:{risk_per_trade:'50',max_positions:3,max_position_value:'2000'}},schedule:{enabled:true,run_time:'10:15',timezone:'America/New_York'},history:{intents:[{symbol:hostile?'<img src=x onerror=alert(1)>':'AAPL',origin:'commissioning',state:'closed',owned_shares:0,entry_usd:'100',stop_usd:'99',target_usd:'102'}],fills:[],total_fills:0,performance:{closed_trades:0,verified:true,net_profit_usd:null}},jobs:[],controls:[]};return r.fulfill({contentType:'application/json',body:JSON.stringify({fields:{payload:{stringValue:JSON.stringify(data)}}})});});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/index.html#atlas-dashboard');
  await page.getByText('Connected to ATLAS',{exact:true}).waitFor();
  assert.match(await page.locator('nav a[aria-current="page"]').innerText(),/ATLAS Dashboard/);
  assert.match(await page.locator('.atlas-metrics').innerText(),/\$20,000\.00/);
  assert.match(await page.locator('#atlas-live-content').innerText(),/0 closed strategy trades · Net Unknown/);
  assert.equal(await page.locator('#atlas-live-content button').count(),0);
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/atlas-live-desktop.png'),fullPage:true});
  for(const width of [390,768]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/atlas-live-mobile.png'),fullPage:true});
  stale=true;
  await page.getByText('Current financial values unknown',{exact:true}).waitFor({timeout:10000});
  assert.doesNotMatch(await page.locator('.atlas-metrics').innerText(),/\$20,000|\$100\.00|\$5\.00/);
  hostile=true;
  await page.getByText('<img src=x onerror=alert(1)>',{exact:true}).waitFor({timeout:10000});
  assert.equal(await page.locator('#atlas-live-content img').count(),0);
  await page.evaluate(()=>window.__authListener(null));
  assert.equal(await page.locator('#atlas-live-content .atlas-live-table').count(),0);
  const atLogout=count;await page.waitForTimeout(5500);assert.equal(count,atLogout);
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(k=>/atlas/i.test(k))),false);
  await page.evaluate(()=>{window.__user.emailVerified=false;window.__authListener(window.__user);});
  await page.waitForTimeout(1000);assert.equal(count,atLogout);
  await page.evaluate(()=>{window.__user.emailVerified=true;window.__authListener(window.__user);});
  await page.locator('.atlas-live-table').first().waitFor({timeout:10000});
  await page.evaluate(()=>{location.hash='#overview';});
  await page.locator('main h1').filter({hasText:'Intelligence with discipline.'}).waitFor();
  const atLeave=count;await page.waitForTimeout(5500);assert.equal(count,atLeave);
  assert.deepEqual(errors,[]);
  console.log('Private ATLAS UI: fresh/stale display, paper scope, escaped history, desktop/mobile, read-only requests, route cleanup, logout and unverified-user denial passed (synthetic auth/data).');
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
