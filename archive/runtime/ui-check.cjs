const { chromium } = require('C:/Users/admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const p=await b.newPage({acceptDownloads:'internal-browser-default',viewport:{width:1440,height:1000}});let errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:5174/');await p.waitForTimeout(2000);console.log(await p.locator('body').innerText());console.log('BUTTONS',await p.locator('button').allTextContents());console.log('ERRORS',errors);await p.screenshot({path:'.runtime/home.png',fullPage:true});await b.close()})().catch(e=>{console.error(e);process.exit(1)});


