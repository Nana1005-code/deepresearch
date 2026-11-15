const {chromium}=require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const context=await browser.newContext({viewport:{width:1500,height:1000},acceptDownloads:true});
  const page=await context.newPage();
  const base='http://127.0.0.1:8000';
  const ids=[]; const checks=[]; let textRequests=0;
  context.on('request',r=>{if(/\/documents\/[^/]+\/text$/.test(r.url())) textRequests++;});
  async function upload(file){
    const chosen=page.waitForEvent('filechooser');
    await page.getByRole('button',{name:'导入文献',exact:false}).click();
    const saved=page.waitForResponse(r=>r.url()===base+'/documents' && r.status()===201);
    await (await chosen).setFiles(file);
    const record=await (await saved).json(); ids.push(record.id);
    await page.locator('.document-row').filter({hasText:record.title}).waitFor();
    return record;
  }
  try{
    await page.goto('http://127.0.0.1:5174');
    const content=Buffer.from(`# 原文件验收 ${Date.now()}\n\n<script>window.injected=true</script>\n**这就是上传的原文件**`);
    const popup=page.waitForEvent('popup');
    const txt=await upload({name:'original-check.md',mimeType:'text/markdown',buffer:content});
    const tab=await popup;
    await tab.waitForURL(`${base}/documents/${txt.id}/original`);
    await tab.locator('pre').waitFor();
    assert.equal(await tab.locator('pre').textContent(),content.toString());
    assert.equal(await tab.evaluate(()=>window.injected),undefined);
    assert.deepEqual(await (await context.request.get(tab.url())).body(),content);
    checks.push('上传 Markdown 后直接打开后端原文件 URL，字节一致，HTML 不执行');
    const manual=page.waitForEvent('popup');
    await page.locator('.document-row').filter({hasText:txt.title}).locator('.preview-link').click();
    const manualTab=await manual;
    await manualTab.waitForURL(`${base}/documents/${txt.id}/original`);
    checks.push('查看原文件按钮直接打开原文件');
    const pdfPopup=page.waitForEvent('popup');
    const pdf=await upload(path.join(__dirname,'original-check.pdf'));
    const pdfTab=await pdfPopup;
    await pdfTab.waitForURL(`${base}/documents/${pdf.id}/original`);
    const pdfResponse=await context.request.get(pdfTab.url());
    assert.equal(pdfResponse.headers()['content-type'],'application/pdf');
    assert.ok(pdfResponse.headers()['content-disposition'].startsWith('inline'));
    assert.deepEqual(await pdfResponse.body(),fs.readFileSync(path.join(__dirname,'original-check.pdf')));
    const range=await context.request.get(pdfTab.url(),{headers:{Range:'bytes=0-99'}});
    assert.equal(range.status(),206);
    checks.push('PDF 原字节、inline 响应和 Range 分段读取通过，浏览器打开原文件地址');
    const before=context.pages().length;
    const word=await upload(path.join(__dirname,'original-check.docx'));
    assert.equal(context.pages().length,before);
    const downloadPromise=page.waitForEvent('download');
    await page.locator('.document-row').filter({hasText:word.title}).getByRole('link',{name:`下载 ${word.title} 原文件`,exact:true}).click();
    const download=await downloadPromise;
    assert.equal(download.suggestedFilename(),'original-check.docx');
    assert.deepEqual(fs.readFileSync(await download.path()),fs.readFileSync(path.join(__dirname,'original-check.docx')));
    checks.push('Word 显示下载原文件入口，下载字节一致，没有空白阅读页');
    assert.equal(textRequests,0);
    checks.push('整个流程没有请求全文提取接口');
    fs.writeFileSync(path.join(__dirname,'original-preview-check.json'),JSON.stringify({passed:true,checks},null,2));
    console.log(JSON.stringify({passed:true,checks},null,2));
  }finally{
    for(const id of ids) await context.request.delete(`${base}/documents/${id}`);
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exit(1);});
