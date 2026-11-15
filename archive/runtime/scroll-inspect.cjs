const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  await page.goto('http://127.0.0.1:5174');
  await page.locator('.home-sidebar .history-open').first().click();
  await page.locator('.quality-entry:visible').first().click();
  await page.locator('.rqg-issue').first().waitFor();
  async function state(selector){return page.locator(selector).first().evaluate(el=>{const rows=[];for(let node=el;node;node=node.parentElement){const css=getComputedStyle(node);rows.push({tag:node.tagName,cls:node.className,top:node.getBoundingClientRect().top,y:node.scrollTop,h:node.clientHeight,sh:node.scrollHeight,overflow:css.overflowY});}return {windowY:scrollY,rows};});}
  console.log('REPORT_BEFORE',JSON.stringify(await state('.research-content')));
  await page.locator('.rqg-issue').first().click();
  await page.waitForTimeout(750);
  console.log('REPORT_AFTER',JSON.stringify(await state('.research-content')));
  await page.goto('http://127.0.0.1:5174');
  await page.locator('.square-entry').click();
  await page.locator('.square-page .research-items section').first().waitFor();
  console.log('SQUARE',JSON.stringify(await state('.square-page')));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
