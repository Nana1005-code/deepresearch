const { chromium } = require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const context = await browser.newContext({viewport:{width:1600,height:1050}});
  const page = await context.newPage();
  const api = context.request;
  const base = 'http://127.0.0.1:8000';
  const created = [];
  const checks = [];
  const nonce = Date.now();
  const contents = `文献预览浏览器验收 ${nonce}\n\n原始文本中的空行保留。\n<script>window.previewInjected=true</script>\n` + '长文本内容应完整呈现，不重复检索片段。\n'.repeat(160);
  page.on('response', async response => {
    if (response.url() === base + '/documents' && response.status() === 201) {
      created.push((await response.json()).id);
    }
  });
  async function upload(files) {
    const choice = page.waitForEvent('filechooser');
    await page.getByRole('button', {name:'导入文献', exact:false}).click();
    await (await choice).setFiles(files);
  }
  async function waitUploaded() {
    await page.locator('.library-message').filter({hasText:'成功导入'}).waitFor();
  }
  try {
    await page.goto('http://127.0.0.1:5174');
    await page.locator('.local-library').waitFor();
    const popupPromise = page.waitForEvent('popup');
    await upload({name:`preview-${nonce}.txt`,mimeType:'text/plain',buffer:Buffer.from(contents)});
    const reader = await popupPromise;
    await reader.locator('.document-text').waitFor();
    assert.equal(await reader.locator('.document-text').textContent(), contents);
    assert.equal(await reader.evaluate(()=>window.previewInjected), undefined);
    assert.equal(await reader.evaluate(()=>window.opener), null);
    await waitUploaded();
    checks.push('上传后自动打开新标签页；全文和换行一致；HTML 作为纯文本；无 opener');
    await reader.reload();
    await reader.locator('.document-text').waitFor();
    assert.equal(await reader.locator('.document-text').textContent(), contents);
    checks.push('独立阅读 URL 刷新后仍可访问');
    await reader.screenshot({path:path.join(__dirname,'document-reader-desktop.png'),fullPage:true});
    await reader.setViewportSize({width:375,height:800});
    assert.equal(await reader.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await reader.screenshot({path:path.join(__dirname,'document-reader-mobile.png'),fullPage:true});
    checks.push('375px 阅读页无横向溢出');
    const row = page.locator('.document-row').filter({hasText:`preview-${nonce}.txt`});
    const selected = await row.locator('input').isChecked();
    const reopened = page.waitForEvent('popup');
    await row.locator('.preview-link').click();
    const second = await reopened;
    await second.locator('.document-text').waitFor();
    assert.equal(await row.locator('input').isChecked(),selected);
    checks.push('查看文本重新打开新标签页，研究勾选状态保持');
    await page.locator('.local-library').screenshot({path:path.join(__dirname,'document-picker.png')});

    await page.evaluate(()=>{window.originalOpen=window.open;window.open=()=>null;});
    await upload({name:`blocked-${nonce}.md`,mimeType:'text/markdown',buffer:Buffer.from(`# 弹窗拦截 ${nonce}\n手动查看入口仍然可用，本地文献应导入成功。`)});
    await page.locator('.library-message').filter({hasText:'文本预览页未打开'}).waitFor();
    const blocked = page.locator('.document-row').filter({hasText:`blocked-${nonce}.md`});
    assert.equal(await blocked.locator('.preview-link').count(),1);
    await page.evaluate(()=>{window.open=window.originalOpen;});
    checks.push('弹窗拦截后上传成功并提示手动查看');

    const failedPopup = page.waitForEvent('popup');
    await upload({name:'empty.txt',mimeType:'text/plain',buffer:Buffer.alloc(0)});
    const failedReader = await failedPopup;
    await page.locator('.library-message').filter({hasText:'上传文件为空'}).waitFor();
    await page.waitForTimeout(150);
    assert.ok(failedReader.isClosed());
    checks.push('上传失败自动关闭等待中的阅读页');

    const batchPopup = page.waitForEvent('popup');
    await upload([
      {name:`batch-a-${nonce}.txt`,mimeType:'text/plain',buffer:Buffer.from(`批量文献第一篇 ${nonce}，验证打开首份成功导入的文本内容。`)},
      {name:`batch-b-${nonce}.txt`,mimeType:'text/plain',buffer:Buffer.from(`批量文献第二篇 ${nonce}，验证其余文献保留手动查看入口。`)}
    ]);
    const batchReader = await batchPopup;
    await batchReader.locator('.document-text').waitFor();
    await page.locator('.library-message').filter({hasText:'已打开首份文献'}).waitFor();
    assert.match(await batchReader.locator('.document-text').textContent(), /第一篇/);
    checks.push('批量上传预览第一份，其他文件保留入口');

    await api.delete(`${base}/documents/${created[0]}`);
    await reader.reload();
    await reader.getByRole('alert').waitFor();
    assert.match(await reader.getByRole('alert').textContent(),/不存在/);
    checks.push('文件删除后阅读页显示明确错误');
    fs.writeFileSync(path.join(__dirname,'document-preview-check.json'),JSON.stringify({passed:true,checks},null,2));
    console.log(JSON.stringify({passed:true,checks},null,2));
  } finally {
    for (const id of created) await api.delete(`${base}/documents/${id}`);
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1);});
