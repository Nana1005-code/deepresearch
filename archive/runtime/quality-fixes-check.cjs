const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const context=await browser.newContext({viewport:{width:1800,height:1000}});const page=await context.newPage();
 const run='9dd4202ad348420a94375af66c23f153';const url='http://127.0.0.1:5174/#research/'+run;const checks=[];const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const button=page.locator('.quality-mark-toggle:visible').first();const root=page.locator('.report-block .markdown-body:visible').first();
 const count=()=>root.locator('[data-rqg-label]').count();
 const top=()=>page.locator('.research-content').evaluateAll(els=>els.forEach(el=>el.scrollTo({top:0,behavior:'instant'})));
 async function panel(){await top();await page.locator('.quality-entry:visible').first().click();await page.locator('.rqg-tabs').waitFor();}
 try{
  const before=await (await context.request.get('http://127.0.0.1:8000/research-runs/'+run)).json();
  await page.goto(url);await button.waitFor();await root.locator('h1').first().waitFor();
  assert.equal(await button.isEnabled(),true);assert.equal(await page.locator('.rqg-panel').count(),0);
  const original=await root.innerHTML();const originalText=await root.textContent();
  const styles=await page.locator('.report-block .document-actions .note-action,.report-block .document-actions .export-btn').evaluateAll(els=>els.filter(e=>e.getClientRects().length).map(e=>{const s=getComputedStyle(e);return {label:e.textContent.trim(),height:e.getBoundingClientRect().height,font:s.fontSize,radius:s.borderRadius,padding:s.padding,bg:s.backgroundColor};}));
  assert.ok(styles.length>=5);for(const s of styles){assert.equal(s.height,32);assert.equal(s.font,'12px');assert.equal(s.radius,'7px');assert.equal(s.padding,'6px 10px');}
  checks.push({check:'shared toolbar styles',styles});
  await button.click();await page.waitForFunction(()=>document.querySelector('.quality-mark-toggle[aria-pressed="true"]')&&document.querySelector('.rqg-inline-badge'));
  const marks=await count();assert.ok(marks>0);assert.equal(await root.textContent(),originalText);checks.push({check:'mark directly without opening audit; text offsets unchanged',marks});
  await button.click();assert.equal(await count(),0);assert.equal(await root.innerHTML(),original);checks.push({check:'toggle off restores original DOM'});
  await button.click();await panel();await page.getByRole('button',{name:'角标+底色',exact:true}).click();await page.getByRole('button',{name:'关闭质检面板（保留原文标记）'}).click();
  assert.equal(await root.getAttribute('data-rqg-style'),'fill');assert.equal(await count(),marks);
  // Delay the reading highlights response so it re-renders after marker restoration.
  await page.route('**/reading/**',async route=>{const response=await route.fetch();const data=await response.json();await new Promise(r=>setTimeout(r,1200));await route.fulfill({response,json:{...data,marks:[{start:0,end:6,text:'test'}]}});});
  await page.reload();await button.waitFor();await root.locator('mark').first().waitFor();await page.waitForFunction(()=>!!document.querySelector('.rqg-inline-badge'));
  assert.equal(await button.getAttribute('aria-pressed'),'true');assert.equal(await root.getAttribute('data-rqg-style'),'fill');assert.equal(await count(),marks);
  checks.push({check:'markers survive reload and asynchronous saved-highlight render'});
  await page.unroute('**/reading/**');await page.reload();await button.waitFor();await page.waitForFunction(()=>!!document.querySelector('.rqg-inline-badge'));
  await panel();assert.equal(await page.locator('.rqg-score-ring strong').textContent(),'82');
  await page.getByRole('tab',{name:/^参考文献 /}).click();assert.equal(await page.locator('.rqg-ref').count(),25);
  assert.equal(await page.locator('.rqg-ref-status').getByText('链接待修正',{exact:true}).count(),3);
  assert.equal(await page.locator('.rqg-ref-status').getByText('未核验',{exact:true}).count(),0);
  await page.screenshot({path:path.join(__dirname,'quality-reference-repair.png')});
  await page.getByRole('tab',{name:/^问题 /}).click();
  for(let i=0;i<3;i++){
   await page.locator('.rqg-issue').filter({hasText:'链接待修正'}).nth(i).click();await page.locator('.rqg-panel').waitFor({state:'hidden'});
   assert.equal(await root.locator('.rqg-focus').count(),1);await page.waitForTimeout(350);
   assert.equal(await page.locator('.layout-fullscreen').evaluate(e=>e.getBoundingClientRect().top),0);
   if(i<2)await panel();
  }
  checks.push({check:'three source repairs and navigation; page top stable'});
  await top();await button.click();assert.equal(await count(),0);
  await page.reload();await button.waitFor();
  await page.route('**/quality/audit/**',route=>route.fulfill({status:503,json:{detail:'质检服务暂不可用'}}));
  await button.click();await page.locator('.rqg-location-notice').waitFor();assert.equal(await button.getAttribute('aria-pressed'),'false');assert.equal(await button.isEnabled(),true);
  await page.unroute('**/quality/audit/**');await button.click();await page.waitForFunction(()=>!!document.querySelector('.rqg-inline-badge'));checks.push({check:'loading failure leaves switch off and retry succeeds'});
  await button.click();
  const after=await (await context.request.get('http://127.0.0.1:8000/research-runs/'+run)).json();assert.deepEqual(after.events,before.events);assert.deepEqual(errors,[]);
  checks.push({check:'report events unchanged; no browser errors'});
  fs.writeFileSync(path.join(__dirname,'quality-fixes-check.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify(checks,null,2));
 }catch(e){await page.screenshot({path:path.join(__dirname,'quality-fixes-failure.png')});console.error(e);process.exitCode=1;}finally{await browser.close();}
})();
