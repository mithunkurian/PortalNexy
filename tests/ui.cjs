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
 function reference(path){return {collection:n=>reference(path+'/'+n),doc:n=>reference(path+'/'+n),orderBy:()=>reference(path),
 onSnapshot:fn=>{queueMicrotask(()=>fn(path==='forward/current'&&window.__fixture?{exists:true,data:()=>({experiment:'offline-test'})}:path.includes('/strategies/')&&window.__fixture?{exists:true,data:()=>window.__fixture[path.split('/').pop()]}:empty));return ()=>{};},
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
  console.log('UI PASS: desktop/mobile, empty states, management navigation, no legacy commands, allowlisted command route, no JS errors.');
 } finally {if(browser)await browser.close();server.close();}
}
run().catch(e=>{console.error(e);process.exitCode=1;});
