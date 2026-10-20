// node check_report.cjs URL PLAYWRIGHT_MODULE CHROME_EXECUTABLE OUTPUT_DIR
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const [url,modulePath,browserPath,output,localPage='index.html']=process.argv.slice(2);
const {chromium}=require(modulePath);
(async()=>{
  const artifacts=path.join(output,'browser-qa');fs.mkdirSync(artifacts,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:browserPath});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[],external=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
    const ready=async(video,frame)=>page.waitForFunction(({video,frame})=>{
      const image=document.querySelector('#frame-image');
      return image&&image.dataset.video===String(video)&&image.dataset.frame===String(frame)&&image.getAttribute('aria-busy')==='false'&&image.style.visibility!=='hidden';
    },{video,frame});
    await page.goto(url,{waitUntil:'networkidle'});await ready(2686,0);
    assert.equal(await page.locator('#scores tbody tr').count(),12);
    assert.equal(await page.locator('#scores tbody tr').first().locator('td').first().innerText(),'35.6');
    await page.screenshot({path:path.join(artifacts,'scores-desktop.png')});
    for(const [video,last] of [[2686,29],[2744,47],[2689,53],[2718,59],[2692,14]]){
      await page.selectOption('#video-select',String(video));await ready(video,0);
      await page.locator('#frame-range').fill(String(last));await ready(video,last);
      assert.equal(await page.locator('#next').isDisabled(),true);
      await page.locator('#prev').click();await ready(video,last-1);
    }
    await page.selectOption('#video-select','2744');await ready(2744,0);
    await page.locator('#frame-range').fill('17');await ready(2744,17);
    if(await page.locator('#language-toggle').count()){
      const theme=await page.locator('html').getAttribute('data-theme');
      await page.locator('#language-toggle').click();await ready(2744,17);
      assert.equal(await page.locator('html').getAttribute('lang'),'en');
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
      const visible=(await page.locator('body').innerText()).replace('中文','');
      assert.equal(/[\u4e00-\u9fff]/.test(visible),false);
      await page.locator('#language-toggle').click();await ready(2744,17);
    }
    for(const width of [1440,768,390,320]){
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow at ${width}`);
      await page.locator('#viewer').scrollIntoViewIfNeeded();
      if(width===1440||width===390)await page.screenshot({path:path.join(artifacts,`viewer-${width}.png`)});
    }
    await page.setViewportSize({width:1440,height:1100});
    await page.locator('[data-jump-video="2686"]').first().click();
    await page.waitForFunction(()=>document.querySelector('#frame-image').dataset.video==='2686');
    const localLinks=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.href).filter(h=>/^http/.test(h)&&new URL(h).origin===location.origin));
    for(const href of localLinks)assert.equal((await page.request.get(href)).ok(),true,href);
    // Actual H.264 decode and seek, not only checking filenames.
    const movie=page.locator('#video-2744 video');
    await page.locator('#video-2744 details summary').click();
    await movie.evaluate(v=>v.load());
    await page.waitForFunction(()=>document.querySelector('#video-2744 video').readyState>=2);
    assert.equal(await movie.evaluate(v=>v.videoWidth),852);
    await movie.evaluate(v=>{v.currentTime=2;});
    await page.waitForFunction(()=>Math.abs(document.querySelector('#video-2744 video').currentTime-2)<.1);
    await page.goto(pathToFileURL(path.join(output,localPage)).href);await ready(2686,0);
    await page.locator('#next').click();await ready(2686,1);
    const noJs=await browser.newContext({javaScriptEnabled:false});const fallback=await noJs.newPage();
    await fallback.goto(pathToFileURL(path.join(output,localPage)).href);
    assert.equal(await fallback.locator('#viewer-controls').isVisible(),false);
    assert.equal(await fallback.locator('#frame-image').evaluate(i=>i.complete&&i.naturalWidth>0),true);
    assert.equal(await fallback.locator('#scores tbody tr').count(),12);
    await noJs.close();
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log(JSON.stringify({status:'passed',videos:5,allEndpoints:true,scoresMatch:true,localLinks:true,videoDecoded:true,responsive:[1440,768,390,320],fileURL:true,noJavaScript:true,pageErrors:errors,externalRequests:external}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
