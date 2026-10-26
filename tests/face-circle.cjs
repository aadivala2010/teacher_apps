// Run with Playwright available: node tests/face-circle.cjs [local app URL]
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const output = path.join(os.tmpdir(), 'teacher-face-circle-test');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto((process.argv[2] || 'http://127.0.0.1:8001') + '/#face-circle');
    await page.waitForFunction(() => window.PDFLib && document.querySelector('#faceCircleApp:not([hidden])'));
    assert.equal(await page.locator('[data-app-tab]').count(), 5);
    assert.equal(await page.locator('#faceExport').isDisabled(), true);

    const fixtures = await page.evaluate(() => [false, true].map(portrait => {
      const c = document.createElement('canvas');
      c.width = portrait ? 800 : 1200;
      c.height = portrait ? 1200 : 800;
      const ctx = c.getContext('2d');
      const gradient = ctx.createLinearGradient(0, 0, c.width, c.height);
      gradient.addColorStop(0, '#739bc4');
      gradient.addColorStop(1, '#234c55');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.fillStyle = '#edbb90';
      ctx.beginPath(); ctx.ellipse(c.width / 2, c.height / 2, 170, 230, 0, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = '#34251b';
      for (const x of [-60, 60]) { ctx.beginPath(); ctx.arc(c.width / 2 + x, c.height / 2 - 35, 14, 0, 2 * Math.PI); ctx.fill(); }
      ctx.beginPath(); ctx.arc(c.width / 2, c.height / 2 + 35, 75, 0.2, Math.PI - 0.2); ctx.stroke();
      return c.toDataURL('image/png').split(',')[1];
    }));
    const upload = fixtures.map((data, i) => ({ name: 'student-' + (i + 1) + '.png', mimeType: 'image/png', buffer: Buffer.from(data, 'base64') }));
    await page.locator('#faceFiles').setInputFiles(upload);
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    assert.equal(await page.locator('#faceCounter').innerText(), '1 / 2');
    const crop = () => page.locator('#faceCanvas').evaluate(c => c.toDataURL());
    const initial = await crop();
    await page.locator('#faceZoom').fill('1.75');
    const box = await page.locator('#faceCanvas').boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.6, { steps: 8 });
    await page.mouse.up();
    const adjusted = await crop();
    assert.notEqual(initial, adjusted, 'Drag and zoom change the crop');
    await page.locator('#faceNext').click();
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    assert.equal(await page.locator('#faceZoom').inputValue(), '1');
    await page.locator('#facePrevious').click();
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    assert.equal(await crop(), adjusted, 'Crop persists through carousel navigation');
    await page.locator('#faceCanvas').focus();
    await page.keyboard.press('ArrowLeft');
    assert.notEqual(await crop(), adjusted, 'Keyboard can reposition the photo');
    await page.locator('[data-face-move="up"]').click();
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    await page.locator('#faceCanvas').evaluate(c => { window.testCrop = c.toDataURL(); });
    await fs.writeFile(path.join(output, 'crop.png'), Buffer.from(await page.evaluate(() => window.testCrop.split(',')[1]), 'base64'));
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#faceExport').click();
    const download = await downloadEvent;
    assert.equal(download.suggestedFilename(), 'face-circle.pdf');
    await download.saveAs(path.join(output, 'face-circle.pdf'));
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    await page.locator('#faceReset').click();
    assert.equal(await crop(), initial, 'Reset restores the initial crop');

    // Failed input must preserve already selected photos.
    await page.locator('#faceFiles').setInputFiles({ name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('invalid image') });
    await page.waitForFunction(() => document.querySelector('#faceStatus').textContent.includes('Could not open'));
    assert.equal(await page.locator('#faceThumbnails button').count(), 2);
    await page.locator('#faceFiles').setInputFiles(upload[0]);
    await page.waitForFunction(() => document.querySelector('#faceCounter').textContent === '3 / 3' && !document.querySelector('#faceExport').disabled);
    await page.locator('#faceRemove').click();
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    assert.equal(await page.locator('#faceCounter').innerText(), '2 / 2');

    for (const viewport of [{ width: 375, height: 812 }, { width: 812, height: 375 }]) {
      await page.setViewportSize(viewport);
      await page.emulateMedia({ reducedMotion: 'reduce' });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const circle = await page.locator('#faceCanvas').boundingBox();
      assert.ok(circle.x >= 0 && circle.x + circle.width <= viewport.width, 'Circle stays inside the mobile viewport');
    }
    await page.setViewportSize({ width: 375, height: 812 });
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    // Send real touch input so pointer capture is exercised too.
    await page.locator('#faceZoom').fill('2');
    const beforeTouch = await crop();
    await page.locator('#faceCanvas').scrollIntoViewIfNeeded();
    const touchBox = await page.locator('#faceCanvas').boundingBox();
    const x = touchBox.x + touchBox.width / 2, y = touchBox.y + touchBox.height / 2;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: x + 25, y: y + 20 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    assert.notEqual(await crop(), beforeTouch);
    await page.locator('#faceClear').click();
    assert.equal(await page.locator('#faceExport').isDisabled(), true);
    assert.equal(await page.locator('#faceThumbnails button').count(), 0);
    for (const name of ['planner', 'activity-descriptor', 'grid', 'grid-print', 'face-circle']) {
      await page.locator('[data-app-tab="' + name + '"]').click();
      assert.equal(await page.locator('[data-app-view="' + name + '"]').isVisible(), true);
    }
    assert.deepEqual(errors, []);
    console.log('PASS: selection, drag, zoom, crop persistence, keyboard, export, reset, invalid input, add/remove, mobile, touch, clear, and all five tabs.');
    console.log('Artifacts: ' + output);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
