const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const results=[];
 try{
  for(const width of [1600,1280]){
   const page=await browser.newPage({viewport:{width,height:900}});
   await page.goto('http://127.0.0.1:5174');
   await page.locator('.home-sidebar .history-open').first().click();
   for(const tab of ['issues','references']){
    await page.locator('.quality-entry:visible').first().click();
    await page.locator('.rqg-tabs').waitFor();
    if(tab==='references')await page.getByRole('tab',{name:/^参考文献 /}).click();
    await page.locator(tab==='issues'?'.rqg-issue':'.rqg-ref').first().click();
    await page.locator('.rqg-panel').waitFor({state:'hidden'});
    await page.waitForFunction(()=>{
     const pane=document.querySelector('.research-content');const hit=pane.querySelector('.rqg-focus');
     if(!hit)return false;const a=pane.getBoundingClientRect(),b=hit.getBoundingClientRect();
     return b.top>=a.top+60&&b.top<a.bottom&&b.bottom<=a.bottom+1;
    });
    const offsets=await page.locator('.research-content').evaluate(el=>{
     const rows=[];for(let n=el.parentElement;n;n=n.parentElement)rows.push({className:n.className,y:n.scrollTop});
     return {outer:rows,report:el.scrollTop,layoutTop:document.querySelector('.layout-fullscreen').getBoundingClientRect().top};
    });
    assert.ok(offsets.report>0);assert.equal(offsets.layoutTop,0);assert.ok(offsets.outer.every(row=>row.y===0));
    results.push({width,check:`${tab} jump scrolls only report`,passed:true});
    await page.locator('.research-content').evaluate(el=>el.scrollTo({top:0,behavior:'instant'}));
    assert.equal(await page.locator('.research-content').evaluate(el=>el.scrollTop),0);
    assert.equal(await page.locator('.layout-fullscreen').evaluate(el=>el.getBoundingClientRect().top),0);
   }
   await page.goto('http://127.0.0.1:5174');
   await page.locator('.square-entry').click();
   await page.locator('.square-page .research-items section').first().waitFor();
   for(const source of ['local','openalex']){
    await page.locator('.mode-switch select').selectOption(source);
    await page.locator(source==='local'?'.research-items:not(.openalex-items) section':'.openalex-items section').first().waitFor();
    const state=await page.locator('.square-page').evaluate(el=>({innerOverflow:getComputedStyle(el).overflowY,innerY:el.scrollTop,innerH:el.clientHeight,innerSH:el.scrollHeight,outerH:document.querySelector('.app-shell').clientHeight,outerSH:document.querySelector('.app-shell').scrollHeight,bodyOverflow:document.documentElement.scrollHeight>innerHeight}));
    assert.equal(state.innerOverflow,'visible');assert.equal(state.innerH,state.innerSH);assert.ok(state.outerSH>state.outerH);assert.equal(state.bodyOverflow,false);
    await page.mouse.move(width-200,250);await page.mouse.wheel(0,650);
    await page.waitForFunction(()=>document.querySelector('.app-shell').scrollTop>100);
    assert.equal(await page.locator('.square-page').evaluate(el=>el.scrollTop),0);
    const shell=page.locator('.app-shell');
    await shell.evaluate(el=>el.scrollTo({top:el.scrollHeight,behavior:'instant'}));
    const bottom=await shell.evaluate(el=>({y:el.scrollTop,max:el.scrollHeight-el.clientHeight}));
    assert.ok(Math.abs(bottom.y-bottom.max)<=1);
    await shell.evaluate(el=>el.scrollTo({top:0,behavior:'instant'}));
    results.push({width,check:`${source} graph has one outer scrollbar and reaches both ends`,passed:true});
    // Exercise the graph component's selection event; rendering remains real.
    await page.waitForFunction(()=>document.querySelector('.topic-graph-shell')?.__vueParentComponent?.props?.data?.nodes?.length>0);
    await shell.evaluate(el=>el.scrollTop=350);
    await page.locator('.topic-graph-shell').evaluate(el=>{const vm=el.__vueParentComponent;vm.emit('select',vm.props.data.nodes[0]);});
    const detail=page.locator(source==='local'?'.detail-page':'.topic-detail-page');
    await detail.locator('h1').waitFor();
    assert.equal(await detail.evaluate(el=>getComputedStyle(el).overflowY),'visible');
    assert.equal(await shell.evaluate(el=>el.scrollTop),0);
    await shell.evaluate(el=>el.scrollTop=250);
    await detail.getByRole('button',{name:/返回/}).first().click();
    await page.locator('.square-page').waitFor();
    assert.equal(await shell.evaluate(el=>el.scrollTop),0);
    results.push({width,check:`${source} topic navigation resets outer scroll`,passed:true});
   }
   await page.screenshot({path:path.join(__dirname,`graph-single-scroll-${width}.png`),fullPage:false});
   await page.close();
  }
  fs.writeFileSync(path.join(__dirname,'scroll-ui-check.json'),JSON.stringify({passed:true,results},null,2));
  console.log(JSON.stringify({passed:true,checks:results.length,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
