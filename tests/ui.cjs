const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const root=path.resolve(__dirname,'../public');
const mock=`window.firebase={initializeApp:()=>{},auth:Object.assign(()=>({
currentUser:window.__user||null,
onAuthStateChanged:fn=>{window.__authListener=fn;queueMicrotask(()=>fn(window.__user||null));},
signOut:()=>{window.__authListener(null);return Promise.resolve();},
signInWithPopup:()=>Promise.reject({code:'auth/popup-closed-by-user',message:'closed'})
}),{GoogleAuthProvider:function(){}})};`;
async function main(){
 const server=http.createServer((req,res)=>{
  const file=path.resolve(root,'.'+(req.url==='/'?'/index.html':req.url.split('?')[0]));
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));
 });
 await new Promise(r=>server.listen(8766,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'chromium',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/firebasejs/**',r=>r.fulfill({contentType:'text/javascript',body:mock}));
  await context.addInitScript(()=>{window.__user={uid:'offline',email:'mithunkurian@gmail.com',displayName:'Founder'};localStorage.setItem('portalnexy-strategy-draft:offline','preserved draft');});
  const page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto('http://127.0.0.1:8766/',{waitUntil:'networkidle'});
  await page.locator('#portal-app').waitFor({state:'visible'});
  assert.equal(await page.locator('main h1').innerText(),'Development Journal.');
  assert.equal(await page.locator('nav a').count(),3);
  assert.equal(await page.locator('#sidebar .brand-mark').count(),0);
  assert.match(await page.locator('#sidebar .brand').innerText(),/nexy/);
  assert.equal(await page.locator('#user-name').innerText(),'Founder');
  assert.equal(await page.evaluate(()=>localStorage.getItem('portalnexy-strategy-draft:offline')),'preserved draft');
  assert.equal(requests.some(url=>/firestore|alpaca|ibkr|forward|option-lab/i.test(url)),false);
  assert.equal(await page.locator('[id^="page-"]').count(),0);
  assert.equal(await page.locator('.milestone').count(),6);
  assert.equal(await page.locator('.milestone.validated').count(),2);
  assert.equal(await page.locator('.timeline-entry').count(), await page.evaluate(()=>NEXY_JOURNAL.log.length + NEXY_JOURNAL.milestones.filter(m=>m.state!=='validated').length));
  await page.getByRole('button',{name:'Upcoming',exact:true}).click();
  assert.equal(await page.locator('.timeline-entry').count(),4);
  await page.getByRole('button',{name:'Recorded work',exact:true}).click();
  assert.equal(await page.locator('.timeline-entry').count(),await page.evaluate(()=>NEXY_JOURNAL.log.length));
  await page.getByRole('searchbox',{name:'Search journal'}).fill('Fresh cash/position acceptance');
  assert.equal(await page.locator('.timeline-entry').count(),1);
  await page.locator('.timeline-entry summary').click();
  assert.match(await page.locator('.timeline-entry p').innerText(),/receipt and comparison validated/);
  await page.getByRole('searchbox',{name:'Search journal'}).fill('no-such-journal-entry');
  assert.equal(await page.locator('.timeline-entry').count(),0);
  await page.getByRole('searchbox',{name:'Search journal'}).fill('');
  await page.getByRole('button',{name:'All entries',exact:true}).click();
  assert.match(await page.locator('.source-card').innerText(),/static snapshot/);
  await page.getByRole('link',{name:'Overview',exact:true}).click();
  await page.locator('main h1').filter({hasText:'Intelligence with discipline.'}).waitFor();
  assert.equal(await page.locator('main h1').innerText(),'Intelligence with discipline.');
  await page.getByRole('link',{name:'Open development journal'}).click();
  await page.locator('#journal-search').waitFor();
  fs.mkdirSync(path.resolve(__dirname,'../.firebase/ui-qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/nexy-journal-desktop.png'),fullPage:true});
  for(const width of [390,320]){
   await page.setViewportSize({width,height:844});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.getByRole('button',{name:'Open navigation'}).click();
   assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'true');
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'false');
  }
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/nexy-journal-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await context.route('https://raw.githubusercontent.com/mithunkurian/ATLAS/main/dashboard/progress.json',r=>r.abort());
  await page.getByRole('link',{name:'Development Tracker',exact:true}).click();
  await page.locator('#atlas-refresh-status').filter({hasText:'Latest status unavailable'}).waitFor();
  assert.equal(await page.locator('main h1').innerText(),'Development Tracker');
  assert.equal(await page.locator('.atlas-milestone').count(),8);
  assert.equal(await page.locator('.atlas-features li').count(),29);
  assert.equal(await page.locator('.atlas-milestone[open]').count(),1);
  assert.match(await page.locator('.atlas-next').innerText(),/M2.1/);
  assert.match(await page.locator('.atlas-summary').innerText(),/unknown/);
  assert.match(await page.locator('.atlas-milestone[open]').innerText(),/stale/i);
  await page.locator('#atlas-status').selectOption('Complete');
  assert.equal(await page.locator('.atlas-milestone').count(),1);
  await page.locator('#atlas-status').selectOption('all');
  await page.locator('#atlas-search').fill('NASDAQ');
  assert.equal(await page.locator('.atlas-milestone').count(),1);
  await page.locator('#atlas-search').fill('no-such-atlas-feature');
  assert.match(await page.locator('#atlas-milestones').innerText(),/No milestones match/);
  await page.locator('#atlas-search').fill('');
  const realEvidence=await page.evaluate(()=>window.ATLAS_TRACKER.progress.milestones[1].evidence);
  await context.unroute('https://raw.githubusercontent.com/mithunkurian/ATLAS/main/dashboard/progress.json');
  await context.route('https://raw.githubusercontent.com/mithunkurian/ATLAS/main/dashboard/progress.json',async r=>{
    const snapshot=await page.evaluate(()=>window.ATLAS_TRACKER.progress);
    snapshot.milestones[1].evidence='Fresh public tracker <img src=x onerror=alert(1)>';
    await r.fulfill({json:snapshot});
  });
  await page.getByRole('button',{name:'Refresh latest status',exact:true}).click();
  await page.locator('#atlas-refresh-status').filter({hasText:'Latest status retrieved'}).waitFor();
  assert.equal(await page.locator('#atlas-milestones img').count(),0);
  assert.match(await page.locator('.atlas-milestone[open]').innerText(),/Fresh public tracker <img/);
  await page.evaluate(evidence=>{atlasLatest.progress.milestones[1].evidence=evidence;renderWorkspace();},realEvidence);
  fs.mkdirSync(path.resolve(__dirname,'../.firebase/ui-qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/atlas-tracker-desktop.png'),fullPage:true});
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.getByRole('button',{name:'Open navigation'}).click();
    await page.getByRole('link',{name:'Development Tracker',exact:true}).click();
    assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'false');
  }
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/atlas-tracker-mobile.png'),fullPage:true});
  await page.reload({waitUntil:'networkidle'});
  assert.equal(await page.locator('main h1').innerText(),'Development Tracker');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  assert.equal(await page.locator('#portal-app').isVisible(),false);
  assert.equal(await page.locator('#login-screen').isVisible(),true);
  await page.getByRole('button',{name:'Sign in with Google'}).click();
  await page.locator('#login-error').waitFor({state:'visible'});
  assert.match(await page.locator('#login-error-msg').innerText(),/Sign-in window closed/);
  assert.equal(await page.getByRole('button',{name:'Sign in with Google'}).isEnabled(),true);
  await page.evaluate(()=>{auth.signInWithPopup=()=>{window.__authListener(window.__user);return Promise.resolve();};});
  await page.getByRole('button',{name:'Sign in with Google'}).click();
  assert.equal(await page.locator('#portal-app').isVisible(),true);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Sign in with Google'}).isEnabled(),true);
  await page.evaluate(()=>window.__authListener({email:'outsider@example.com'}));
  assert.equal(await page.locator('#portal-app').isVisible(),false);
  assert.match(await page.locator('#login-error-msg').innerText(),/Access denied/);
  assert.deepEqual(errors,[]);
  console.log('ATLAS tracker and Nexy journal PASS: eight milestones/29 features, search/status filters, GitHub refresh/fallback, escaped content, direct route, responsive layouts;  milestones, timeline search/filters, navigation, desktop/mobile, founder access, sign-out, login errors, no trading or data requests.');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
