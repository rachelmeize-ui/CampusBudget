// Optional browser verification. Install Playwright separately, or pass its module path.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.argv[2] || 'playwright');
let launchedBrowser;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CAMPUSBUDGET_CHROME || undefined,
  });
  launchedBrowser=browser;
  const context = await browser.newContext({viewport:{width:1440,height:1320},deviceScaleFactor:1});
  const page = await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const target=process.env.CAMPUSBUDGET_URL || 'http://127.0.0.1:8503';
  const images=path.resolve(__dirname,'..','docs','images');
  fs.mkdirSync(images,{recursive:true});
  await page.goto(target,{waitUntil:'domcontentloaded'});
  await page.getByText('这个月，花得心里有数。',{exact:true}).waitFor({timeout:45000});
  await page.locator('.js-plotly-plot').first().waitFor();
  await page.screenshot({path:path.join(images,'overview.png'),fullPage:true});
  console.log('Overview ready.');
  const go=async name=>page.locator('[data-testid="stSidebar"]').getByText(name,{exact:true}).click();
  await go('记一笔');
  await page.getByRole('textbox',{name:'这一笔是什么？',exact:true}).fill('2026-05-10 奶茶 15');
  await page.getByRole('button',{name:'解析这笔记录',exact:true}).click();
  await page.getByRole('button',{name:'确认并保存',exact:true}).waitFor();
  const amount=await page.getByRole('spinbutton',{name:'确认金额 / 元',exact:true}).inputValue();
  if(Number(amount)!==15) throw new Error('Date was incorrectly parsed as the amount.');
  await page.screenshot({path:path.join(images,'entry.png'),fullPage:true});
  await go('消费分析');
  await page.getByText('支出从哪里开始关注',{exact:true}).waitFor();
  await page.screenshot({path:path.join(images,'analytics.png'),fullPage:true});
  await go('预算管理');
  await page.getByText('安排这个月的生活费',{exact:true}).waitFor();
  await page.screenshot({path:path.join(images,'budget.png'),fullPage:true});
  await go('账本管理');
  await page.getByRole('button',{name:'↓ 导出 CSV',exact:true}).waitFor();
  console.log('All five views rendered. Parser preview passed.');
  console.log('Client errors:',JSON.stringify(errors));
  console.log('Desktop horizontal overflow:',await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));

  const mobile=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
  const phone=await mobile.newPage();
  await phone.goto(target,{waitUntil:'domcontentloaded'});
  await phone.getByText('这个月，花得心里有数。',{exact:true}).waitFor({timeout:45000});
  console.log('Mobile buttons:',await phone.getByRole('button').evaluateAll(nodes=>nodes.map(n=>({text:n.innerText,aria:n.getAttribute('aria-label'),title:n.getAttribute('title')})).slice(0,15)));
  const close=phone.getByRole('button',{name:/^(Close|Collapse) sidebar$/});
  if(await close.count() && await close.isVisible()) {
    await close.click();
    await phone.waitForFunction(()=>{
      const sidebar=document.querySelector('[data-testid="stSidebar"]');
      return !sidebar || sidebar.getBoundingClientRect().right<=1;
    });
  }
  await phone.screenshot({path:path.join(images,'mobile.png'),fullPage:true});
  console.log('Mobile horizontal overflow:',await phone.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  await browser.close();
  if(errors.length) process.exitCode=1;
})().catch(async e=>{console.error(e);await launchedBrowser?.close();process.exitCode=1;});
