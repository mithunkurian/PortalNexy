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
  browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/firebasejs/**',r=>r.fulfill({contentType:'text/javascript',body:mock}));
  await context.addInitScript(()=>{window.__user={uid:'offline',email:'mithunkurian@gmail.com',displayName:'Founder'};localStorage.setItem('portalnexy-strategy-draft:offline','preserved draft');});
  const page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto('http://127.0.0.1:8766/',{waitUntil:'networkidle'});
  await page.locator('#portal-app').waitFor({state:'visible'});
  assert.equal(await page.locator('main h1').innerText(),'PortalNEXY');
  assert.equal(await page.locator('nav a').count(),1);
  assert.equal(await page.locator('#sidebar .brand-mark').count(),0);
  assert.equal(await page.locator('#sidebar .brand').innerText(),'PortalNEXY');
  assert.equal(await page.locator('#user-name').innerText(),'Founder');
  assert.equal(await page.evaluate(()=>localStorage.getItem('portalnexy-strategy-draft:offline')),'preserved draft');
  assert.equal(requests.some(url=>/firestore|alpaca|ibkr|forward|option-lab/i.test(url)),false);
  assert.equal(await page.locator('[id^="page-"]').count(),0);
  fs.mkdirSync(path.resolve(__dirname,'../.firebase/ui-qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/nexydao-desktop.png'),fullPage:true});
  for(const width of [390,320]){
   await page.setViewportSize({width,height:844});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.getByRole('button',{name:'Open navigation'}).click();
   assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'true');
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#menu-button').getAttribute('aria-expanded'),'false');
  }
  await page.screenshot({path:path.resolve(__dirname,'../.firebase/ui-qa/nexydao-mobile.png'),fullPage:true});
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
  console.log('PortalNEXY shell PASS: desktop/mobile, founder access, sign-out, login errors, no trading or data requests.');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
