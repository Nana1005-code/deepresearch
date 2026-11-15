const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const ids=new Set(); const errors=[]; let sends=0;
  page.on('pageerror',e=>errors.push(e.message));
  const request=page.request, backend='http://127.0.0.1:8000';
  const mainBefore=await(await request.get(backend+'/conversations')).json();
  // Exercise real local database queries without invoking the unchanged model provider.
  await page.route('**/research-square/gap-conversations/*/messages',async route=>{
    sends++; ids.add(route.request().url().split('/').at(-2));
    const payload=route.request().postDataJSON();payload.model_profile_id=null;
    await route.continue({postData:JSON.stringify(payload)});
  });
  async function openSquare(){await page.getByRole('button',{name:'◈ 我的研究图谱',exact:true}).click();await page.getByLabel('遗漏助手问题',{exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('[aria-label="遗漏助手问题"]').disabled);}
  const metrics=()=>page.locator('.gap-assistant').evaluate(el=>({height:el.clientHeight,outer:document.querySelector('.app-shell').scrollHeight,width:el.clientWidth,innerHeight:el.querySelector('.gap-messages').clientHeight,innerScroll:el.querySelector('.gap-messages').scrollHeight}));
  try{
    await page.goto('http://127.0.0.1:5174');await openSquare();
    await page.getByLabel('新建遗漏助手对话',{exact:true}).click();
    const before=await metrics();const input=page.getByLabel('遗漏助手问题',{exact:true});
    await input.fill('多模态机器学习应用');await input.press('Shift+Enter');assert.equal(sends,0);assert.ok((await input.inputValue()).includes('\n'));
    await input.fill('多模态机器学习应用');
    await input.dispatchEvent('keydown',{key:'Enter',code:'Enter',isComposing:true});assert.equal(sends,0);
    await input.press('Enter');await page.locator('.gap-suggestion').first().waitFor({timeout:30000});
    await page.waitForFunction(()=>!document.querySelector('[aria-label="遗漏助手问题"]').disabled);
    assert.equal(sends,1);assert.equal(await page.locator('.message.user b').count(),0);
    const after=await metrics();assert.equal(after.height,before.height);assert.equal(after.outer,before.outer);assert.ok(after.innerScroll>after.innerHeight);
    const typography=await page.locator('.gap-suggestion').first().evaluate(el=>({heading:getComputedStyle(el.querySelector('h3')).fontSize,weight:getComputedStyle(el.querySelector('h3')).fontWeight,body:getComputedStyle(el.querySelector('p')).fontSize,bodyWeight:getComputedStyle(el.querySelector('p')).fontWeight,text:el.querySelector('p').textContent}));
    assert.equal(typography.heading,'15px');assert.equal(typography.weight,'700');assert.equal(typography.body,'14px');assert.equal(typography.bodyWeight,'400');
    const id=[...ids][0]; const saved=await(await request.get(backend+'/research-square/gap-conversations/'+id)).json();const suggestion=saved.messages[1].suggestions[0];assert.ok(typography.text.includes(` ${suggestion.cooccurrence_count} 篇`));assert.ok(typography.text.includes(` ${suggestion.my_research_count} 条`));
    await page.locator('.gap-messages').evaluate(el=>el.scrollTop=0);await page.locator('.gap-assistant').screenshot({path:'.runtime/gap-assistant-result.png'});
    await page.getByLabel('新建遗漏助手对话',{exact:true}).click();assert.equal(await page.locator('.gap-suggestion').count(),0);
    await page.getByLabel('遗漏助手历史对话',{exact:true}).click();await page.getByLabel('搜索遗漏助手对话',{exact:true}).fill('多模态机器学习应用');
    await page.locator('.chat-history .conversation-row').first().click();await page.locator('.gap-suggestion').first().waitFor();
    await page.reload();await openSquare();await page.locator('.gap-suggestion').first().waitFor();
    assert.equal(await page.locator('.message.user').count(),1);
    await input.fill('多模态机器学习应用');await input.press('Enter');await page.waitForFunction(()=>document.querySelectorAll('.message.assistant').length===2 && !document.querySelector('[aria-label="遗漏助手问题"]').disabled);
    assert.equal((await metrics()).height,before.height);assert.equal((await metrics()).outer,before.outer);
    await page.getByLabel('遗漏助手历史对话',{exact:true}).click();await page.locator('.chat-history').screenshot({path:'.runtime/gap-assistant-history.png'});
    await page.getByLabel('删除遗漏助手对话：多模态机器学习应用',{exact:true}).click();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.delete-overlay'));
    assert.equal((await request.get(backend+'/research-square/gap-conversations/'+id)).status(),404);
    assert.deepEqual(await(await request.get(backend+'/conversations')).json(),mainBefore);
    assert.equal(await page.locator('#home-conversation-history').innerText(),'');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,before,after,typography,history:'create/search/restore/reload/delete passed',keyboard:'Enter/Shift+Enter/IME passed',homepage:'isolated'},null,2));
  }finally{for(const id of ids)await request.delete(backend+'/research-square/gap-conversations/'+id);await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
