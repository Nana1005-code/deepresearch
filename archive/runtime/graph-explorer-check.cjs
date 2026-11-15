const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1600,height:1000}}),api='http://127.0.0.1:8000';const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
await page.goto('http://127.0.0.1:5174');await page.getByRole('button',{name:'◈ 我的研究图谱',exact:true}).click();await page.locator('.research-items>section').first().waitFor();
const layout=async()=>page.evaluate(()=>{document.querySelector('.app-shell').scrollTop=99999;return new Promise(resolve=>requestAnimationFrame(()=>{const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}};resolve({sidebar:rect('.home-sidebar'),records:rect('.research-list'),assistant:rect('.gap-assistant')})}))});
console.log('layout',JSON.stringify(await layout()));await page.screenshot({path:'.runtime/graph-bottom-alignment.png'});
const local=await(await page.request.get(api+'/research-square/nodes/search?source=local&q='+encodeURIComponent('多模态'))).json();assert.ok(local.length>0);
for(const source of ['local','openalex']){
await page.locator('.mode-switch select').selectOption(source);await page.getByLabel('搜索图谱节点').fill('多模态');await page.locator('.node-results button').first().waitFor();
const matches=await(await page.request.get(api+'/research-square/nodes/search?source='+source+'&q='+encodeURIComponent('多模态'))).json();const match=matches[0];
await page.locator('.node-results button').first().click();await page.locator('.focus-label').waitFor();
const graph=await(await page.request.get(api+`/research-square/nodes/${match.public_id}/graph?source=${source}`)).json();assert.ok(graph.nodes.some(n=>n.id===match.public_id));assert.ok(graph.edges.every(e=>e.source===match.public_id));assert.ok(graph.nodes.length>1);
const detail=await(await page.request.get(api+`/research-square/${source==='local'?'community':'openalex'}/topics/${match.public_id}`)).json();assert.equal(detail.name,match.name);if(source==='local'){assert.ok(detail.description.length>20);assert.ok(!detail.description.includes('AI 关键词归一'));}
console.log(source,'suggestions',matches.length,'neighbors',graph.nodes.length-1);
await page.getByRole('button',{name:'返回完整图谱',exact:true}).click();assert.equal(await page.locator('.focus-label').count(),0);
await page.getByLabel('搜索图谱节点').fill('zzzznotreal239832');await page.getByRole('button',{name:'搜索节点',exact:true}).click();await page.getByText('没有匹配的已存节点，请尝试其他关键词。').waitFor();
}
await page.locator('.mode-switch select').selectOption('local');
await page.route('**/research-square/gap-conversations/*/messages',route=>{const data=route.request().postDataJSON();data.model_profile_id=null;return route.continue({postData:JSON.stringify(data)});});
await page.getByLabel('新建遗漏助手对话',{exact:true}).click();await page.getByLabel('遗漏助手问题',{exact:true}).fill('多模态机器学习应用');await page.getByLabel('遗漏助手问题',{exact:true}).press('Enter');await page.locator('.topic-link').first().waitFor({timeout:30000});
const id=await page.evaluate(()=>localStorage.getItem('research-gap-active-conversation'));const title=await page.locator('.topic-link').first().innerText();await page.locator('.topic-link').first().click();await page.locator('.topic-hero h1').waitFor();assert.ok(title.includes(await page.locator('.topic-hero h1').innerText()));await page.request.delete(api+'/research-square/gap-conversations/'+id);
assert.deepEqual(errors,[]);console.log('PASS search, real neighborhoods, summaries, topic links');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
