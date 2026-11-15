const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const context=await browser.newContext({viewport:{width:1800,height:1050}});
  const page=await context.newPage();
  const base='http://127.0.0.1:8000';
  const checks=[]; const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  async function openPanel(){
    if(!await page.locator('.rqg-panel').count()) await page.locator('.quality-entry:visible').first().click();
    await page.locator('.rqg-tabs').waitFor();
  }
  async function assertLocated(label){
    try { await page.locator('.rqg-panel').waitFor({state:'hidden',timeout:5000}); }
    catch(error){
      console.log('FAILED',label,await page.locator('.rqg-location-notice').allTextContents());
      console.log('ROOTS',await page.locator('.quality-entry').evaluateAll(buttons=>buttons.map(button=>({visible:!!button.getClientRects().length,root:!!button.closest('.document-card')?.querySelector('.markdown-body')}))));
      await page.screenshot({path:path.join(__dirname,'quality-location-failure.png'),fullPage:false});
      throw error;
    }
    const focus=page.locator('.markdown-body .rqg-focus');
    assert.equal(await focus.count(),1,label);
    await focus.waitFor({state:'visible'});
    await page.waitForTimeout(120);
    assert.ok(!await page.locator('.rqg-retry').count(),label);
    return await focus.textContent();
  }
  try{
    const runs=await (await context.request.get(base+'/research-runs')).json();
    for(const index of [0,1,2]){
      const run=runs[index];
      const before=await (await context.request.get(base+'/research-runs/'+run.id)).json();
      const audit=await (await context.request.get(base+'/quality/audit/'+run.id)).json();
      await page.goto('http://127.0.0.1:5174');
      await page.locator('.home-sidebar .history-open').nth(index).click();
      await page.locator('.quality-entry:visible').first().waitFor();
      await page.waitForTimeout(200);
      await openPanel();
      assert.equal(await page.locator('.rqg-issue').count(),audit.issues.length);
      for(let i=0;i<audit.issues.length;i++){
        console.log('CHECK',index,audit.issues[i].type,JSON.stringify(audit.issues[i]));
        await openPanel();
        await page.getByRole('tab',{name:/^问题 /}).click();
        await page.locator('.rqg-issue').nth(i).click();
        const text=await assertLocated(run.id+' '+audit.issues[i].type);
        if(audit.issues[i].type==='missing_conclusion') assert.match(await page.locator('.rqg-location-notice').textContent(),/缺少内容/);
        checks.push({run:run.id,type:'issue',finding:audit.issues[i].type,located:text.slice(0,90)});
      }
      await openPanel();
      await page.getByRole('tab',{name:/^参考文献 /}).click();
      assert.equal(await page.locator('.rqg-ref').count(),audit.references.length);
      if(index===0){
        assert.equal(audit.metrics.references,24);
        assert.ok(audit.references.every(ref=>ref.verified));
        await page.screenshot({path:path.join(__dirname,'quality-references-fixed.png'),fullPage:false});
      }
      for(let i=0;i<audit.references.length;i++){
        await openPanel();
        await page.getByRole('tab',{name:/^参考文献 /}).click();
        await page.locator('.rqg-ref').nth(i).click();
        const text=await assertLocated('reference '+i);
        checks.push({run:run.id,type:'reference',index:i,located:text.slice(0,90)});
      }
      for(let i=0;i<audit.citations.length;i++){
        await openPanel();
        await page.getByRole('tab',{name:/^引用位置 /}).click();
        await page.locator('.rqg-citation').nth(i).click();
        await assertLocated('citation '+i);
      }
      checks.push({run:run.id,citationsLocated:audit.citations.length,references:audit.references.length});
      await openPanel();
      await page.getByRole('tab',{name:'质检单',exact:true}).click();
      await page.getByRole('button',{name:'生成质检单',exact:true}).click();
      await page.locator('.rqg-preview').first().waitFor();
      if(audit.references.length) assert.match(await page.locator('.rqg-preview').first().textContent(),/参考文献核验/);
      const after=await (await context.request.get(base+'/research-runs/'+run.id)).json();
      assert.deepEqual(after.events,before.events);
      checks.push({run:run.id,eventsUnchanged:true});
    }
    await page.goto('http://127.0.0.1:5174');
    const unit=await page.evaluate(async()=>{
      const {QualityMarkerLayer}=await import('/src/components/QualityMarkerLayer.ts');
      const card=document.createElement('div');card.className='document-card';
      card.innerHTML='<button id="unit-anchor">质检</button><div class="markdown-body"><h2>分析</h2><p>第一处 <a href="https://example.test/p?id=1">论文</a>。</p><p class="existing">根据<strong>实验结果</strong>，准确率提升 <em>12%</em>，见 <a href="https://example.test/p?id=2">论文</a>。</p><h2>参考文献</h2><p><a href="https://example.test/p?id=2">论文</a></p></div>';
      document.body.append(card);
      const root=card.querySelector('.markdown-body'); const original=root.outerHTML;
      const layer=new QualityMarkerLayer(card.querySelector('button'));
      layer.refresh(card.querySelector('button'),'## 分析\n第一处论文。\n根据**实验结果**，准确率提升12%，见论文。\n## 参考文献');
      if(!layer.locate({quote:'根据实验结果，准确率提升12%，见论文。',section:'分析'}))throw Error('cross-node quote not located');
      if(!root.querySelector('p.existing.rqg-focus'))throw Error('wrong text target');
      layer.clear(); if(root.outerHTML!==original)throw Error('DOM not restored after text locate');
      layer.apply([{type:'no_source_section',severity:'warn',message:'test',section:'分析'}],[]);
      const badges=root.querySelectorAll('[data-rqg-badge]').length;
      if(!layer.locate({url:'https://example.test/p?id=2',section:'参考文献'}))throw Error('reference not located');
      if(root.querySelector('.rqg-focus').closest('p')!==root.querySelector('p:last-child'))throw Error('wrong duplicate URL target');
      if(root.querySelectorAll('[data-rqg-badge]').length!==badges)throw Error('locate removed persistent marks');
      layer.clear(); if(root.outerHTML!==original)throw Error('DOM not restored after markers');
      layer.locate({url:'https://example.test/p?id=2&utm_source=x',section:'分析'});
      if(!root.querySelector('p.existing .rqg-focus'))throw Error('meaningful query lost');
      layer.clear();card.remove();
      return {crossNode:true,sectionScopedLinks:true,meaningfulQuery:true,markersPreserved:true,domRestored:true};
    });
    assert.deepEqual(errors,[]);
    const summary={passed:true,runs:3,issueClicks:checks.filter(c=>c.type==='issue').length,referenceClicks:checks.filter(c=>c.type==='reference').length,citationClicks:checks.reduce((n,c)=>n+(c.citationsLocated||0),0),unit};
    fs.writeFileSync(path.join(__dirname,'quality-navigation-check.json'),JSON.stringify({summary,checks},null,2));
    console.log(JSON.stringify(summary,null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
