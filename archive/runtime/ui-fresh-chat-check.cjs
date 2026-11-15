const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const c=await b.newContext({viewport:{width:1800,height:1000}});const p=await c.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
try{
 await p.addInitScript(()=>{localStorage.setItem('research-gap-active-conversation','old');localStorage.setItem('research-academic-active-conversation','old');});
 let details=0,posts=0;
 await p.route(/\/research-square\/(?:gap|academic)-conversations(?:\/old)?$/,async route=>{const req=route.request();if(req.method()!=='GET')posts++;const item={id:'old',title:'保留的历史对话',updated_at:new Date().toISOString(),status:'idle',error:null,messages:[{role:'user',content:'历史问题'},{role:'assistant',content:'历史回答'}],message_count:2,preview:'历史问题'};if(req.url().endsWith('/old'))details++;await route.fulfill({json:req.url().endsWith('/old')?item:[item]});});
 await p.goto('http://127.0.0.1:5174');await p.locator('.square-entry').click();
 for(const source of ['local','openalex','local','openalex']){
   await p.locator('.mode-switch select').selectOption(source);await p.locator('.gap-assistant textarea:not(:disabled)').waitFor();
   assert.equal(await p.locator('.conversation-title').count(),0);assert.equal(await p.locator('.gap-assistant textarea').inputValue(),'');
   if(source==='openalex')assert.equal(await p.locator('.academic-examples').count(),1);
   const before=details;await p.locator('.gap-assistant button[title="历史对话"]').click();await p.locator('.conversation-row').click();await p.locator('.conversation-title').waitFor();assert.equal(details,before+1);assert.ok((await p.locator('.gap-messages').textContent()).includes('历史回答'));
 }
 assert.equal(posts,0);console.log('PASS both assistants start new on entry/mode switch; explicit history opens; no empty conversations created');
 const run='f1bc957e273a474e815a4914b2136b7e';const audit=await(await c.request.get('http://127.0.0.1:8000/quality/audit/'+run)).json();audit.references=audit.references.slice(0,3);audit.references[0].authenticity={status:'real',reason:'已核验'};audit.references[1].authenticity={status:'unconfirmed',failure_kind:'unreachable',reason:'链接访问超时'};audit.references[2].authenticity={status:'unconfirmed',failure_kind:'title_mismatch',reason:'页面标题不一致'};
 const calls=[];await p.route('**/quality/audit/**',r=>r.fulfill({json:audit}));await p.route('**/quality/verify-reference/**',r=>{const data=r.request().postDataJSON();calls.push(data.reference_id);return r.fulfill({json:{id:data.reference_id,authenticity:audit.references.find(x=>x.id===data.reference_id).authenticity}})});
 await p.goto('http://127.0.0.1:5174/#research/'+run);await p.locator('.quality-entry:visible').first().click();await p.getByRole('tab',{name:/^参考文献 /}).click();await p.getByRole('button',{name:'重试未通过项'}).waitFor();
 assert.equal(await p.locator('.rqg-ref-status').getByText('真实',{exact:true}).count(),1);assert.equal(await p.locator('.rqg-ref-status').getByText('暂无法访问',{exact:true}).count(),1);assert.equal(await p.locator('.rqg-ref-status').getByText('标题待核对',{exact:true}).count(),1);
 await p.getByRole('button',{name:'重试未通过项'}).click();await p.getByRole('button',{name:'重试未通过项'}).waitFor();assert.ok(!calls.includes(audit.references[0].id));assert.equal(await p.locator('.rqg-ref-status').getByText('真实',{exact:true}).count(),1);assert.deepEqual(errors,[]);console.log('PASS distinct verification failures, retry excludes confirmed real references, no browser errors');
}catch(e){console.error(e);process.exitCode=1;}finally{await b.close();}})();
