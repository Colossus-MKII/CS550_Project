// node check_dataset.cjs URL PLAYWRIGHT_MODULE CHROME_EXECUTABLE ARTIFACT_DIR LOCAL_DIR
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const [url,modulePath,browserPath,artifacts,localDir]=process.argv.slice(2);
const {chromium}=require(modulePath);
(async()=>{
  fs.mkdirSync(artifacts,{recursive:true});
  const manifest=JSON.parse(fs.readFileSync(path.join(localDir,'dataset-samples/manifest.json'),'utf8'));
  const browser=await chromium.launch({headless:true,executablePath:browserPath});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[],external=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
    const ready=async(id,frame)=>{
      await page.waitForFunction(({id,frame})=>{const p=document.querySelector('#dataset-panels');return p?.getAttribute('aria-busy')==='false'&&p.dataset.sample===String(id)&&p.dataset.frame===String(frame)&&!p.classList.contains('failed');},{id,frame});
      assert.match(await page.locator('#dataset-rgb').getAttribute('src'),new RegExp(`${id}/rgb/${String(frame).padStart(5,'0')}\\.png$`));
    };
    await page.goto(url,{waitUntil:'networkidle'});await ready(2686,0);
    assert.equal(await page.locator('#dataset-controls').isVisible(),true);
    assert.equal(await page.locator('#instance-rows tr').count(),4);
    await page.locator('#samples').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(artifacts,'dataset-zh-desktop.png')});
    await page.locator('#frame-next').click();await ready(2686,1);
    await page.locator('#frame-prev').click();await ready(2686,0);
    assert.equal(await page.locator('#frame-prev').isDisabled(),true);
    for(const sample of manifest.samples){
      await page.selectOption('#sample-select',String(sample.id));await ready(sample.id,0);
      for(const frame of [0,sample.frames-1]){
        await page.locator('#dataset-frame').fill(String(frame));await ready(sample.id,frame);
        await page.selectOption('#object-select','0');await page.selectOption('#view-select','binary');
        await page.waitForFunction(()=>document.querySelector('#dataset-panels').getAttribute('aria-busy')==='false'&&document.querySelector('#dataset-panels').dataset.view==='binary');
        const count=await page.locator('#dataset-mask').evaluate(c=>{const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<a.length;i+=4){if(![0,255].includes(a[i])||a[i]!==a[i+1]||a[i]!==a[i+2]||a[i+3]!==255)throw Error('Not a binary mask');if(a[i]===255)n++;}return n;});
        assert.equal(count,sample.channels[0].areas[frame]);
        await page.selectOption('#view-select','overlay');
      }
      assert.equal(await page.locator('#frame-next').isDisabled(),true);
    }
    // A slower earlier image request must never overwrite the newest frame.
    await page.selectOption('#sample-select','2686');await ready(2686,0);
    await page.route('**/2686/**/00002.png',async route=>{await new Promise(r=>setTimeout(r,350));await route.continue();});
    await page.locator('#dataset-frame').fill('2');await page.locator('#dataset-frame').fill('3');await ready(2686,3);
    await page.waitForTimeout(500);assert.equal(await page.locator('#dataset-panels').getAttribute('data-frame'),'3');
    await page.unroute('**/2686/**/00002.png');
    await page.selectOption('#sample-select','2744');await ready(2744,0);
    await page.locator('#dataset-frame').fill('17');await ready(2744,17);
    await page.selectOption('#object-select','2');await page.selectOption('#view-select','binary');
    await page.waitForFunction(()=>document.querySelector('#dataset-panels').dataset.view==='binary'&&document.querySelector('#dataset-panels').getAttribute('aria-busy')==='false');
    await page.locator('#theme-toggle').click();const theme=await page.locator('html').getAttribute('data-theme');
    await page.locator('#language-toggle').click();await ready(2744,17);
    assert.equal(await page.locator('html').getAttribute('lang'),'en');
    assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
    assert.equal(await page.inputValue('#object-select'),'2');assert.equal(await page.inputValue('#view-select'),'binary');
    assert.equal(await page.locator('#frame-play').getAttribute('aria-pressed'),'false');
    await page.selectOption('#view-select','overlay');await ready(2744,17);
    for(const width of [1440,768,390,320]){
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow at ${width}`);
      await page.locator('#samples').scrollIntoViewIfNeeded();
      if(width===1440||width===390)await page.screenshot({path:path.join(artifacts,`dataset-en-${width}.png`)});
    }
    await page.setViewportSize({width:1440,height:1100});
    await page.selectOption('#browse-speed','10');await page.locator('#frame-play').click();
    await page.waitForFunction(()=>Number(document.querySelector('#dataset-panels').dataset.frame)>17);
    await page.locator('#frame-play').click();
    assert.equal(await page.locator('#frame-play').getAttribute('aria-pressed'),'false');
    await page.goto(new URL('dataset.en.html?sample=bad&frame=9999&channel=999&view=bad',url).href);await ready(2686,29);
    assert.equal(await page.inputValue('#object-select'),'all');assert.equal(await page.inputValue('#view-select'),'overlay');
    await page.locator('#frame-play').click();await ready(2686,0);await page.locator('#frame-play').click();
    // HTTP asset failure is explicit, hides stale imagery, and recovers on next frame.
    await page.route('**/2686/rgb/00004.png',route=>route.fulfill({status:404,body:'expected test failure'}));
    await page.locator('#dataset-frame').fill('4');await page.waitForFunction(()=>document.querySelector('#dataset-panels').classList.contains('failed'));
    assert.match(await page.locator('#dataset-status').innerText(),/could not load/);
    await page.unroute('**/2686/rgb/00004.png');await page.locator('#dataset-frame').fill('5');await ready(2686,5);
    // Works as a local document, without fetch or reading tainted canvas pixels.
    await page.goto(pathToFileURL(path.join(localDir,'dataset.html')).href);await ready(2686,0);
    await page.locator('#dataset-frame').fill('12');await ready(2686,12);
    await page.selectOption('#view-select','binary');await page.waitForFunction(()=>document.querySelector('#dataset-panels').dataset.view==='binary');
    const noJs=await browser.newContext({javaScriptEnabled:false});const fallback=await noJs.newPage();
    for(const name of ['dataset.html','dataset.en.html']){
      await fallback.goto(pathToFileURL(path.join(localDir,name)).href);
      assert.equal(await fallback.locator('#dataset-controls').isVisible(),false);
      for(const id of ['dataset-rgb','dataset-poster'])assert.equal(await fallback.locator('#'+id).evaluate(i=>i.complete&&i.naturalWidth>0),true);
      assert.match(await fallback.locator('#coverage').innerText(),/226/);
    }
    await noJs.close();
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log(JSON.stringify({status:'passed',realSamples:5,exportedFrames:207,binaryPixelCounts:'exact',raceGuard:true,bilingualState:true,responsive:[1440,768,390,320],offline:true,noJavaScriptFallback:true,errorRecovery:true,pageErrors:errors,externalRequests:external}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
