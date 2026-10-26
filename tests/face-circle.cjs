// Run with Playwright available: node tests/face-circle.cjs [local app URL]
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');
const { PDFDocument } = require('../public/vendor/pdf-lib-1.17.1.min.js');

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
    assert.equal(await page.locator('#faceSize').getAttribute('min'), '0.5');
    assert.equal(await page.locator('#faceSize').getAttribute('step'), '0.25');
    assert.equal(await page.locator('#faceSize').inputValue(), '3');
    await page.locator('#faceSize').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#faceSize').inputValue(), '3.25');
    await page.locator('#faceSize').fill('3');

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
    const initialPreview = await page.locator('#facePagePreview').evaluate(c => c.toDataURL());
    await page.locator('#faceZoom').fill('1.75');
    const box = await page.locator('#faceCanvas').boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.6, { steps: 8 });
    await page.mouse.up();
    const adjusted = await crop();
    assert.notEqual(initial, adjusted, 'Drag and zoom change the crop');
    assert.notEqual(await page.locator('#facePagePreview').evaluate(c => c.toDataURL()), initialPreview, 'Page preview tracks crop changes');
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
    for (const inches of [0.5, 3.25, 8]) {
      const beforeResize = await crop();
      await page.locator('#faceSize').fill(String(inches));
      assert.equal(await crop(), beforeResize, 'Print size keeps the existing face crop');
      assert.equal(await page.locator('#faceSizeValue').innerText(), inches + ' in');
      assert.ok((await page.locator('#facePagePreview').getAttribute('aria-label')).includes(inches + '-inch circle'));
      const event = page.waitForEvent('download');
      await page.locator('#faceExport').click();
      const sizedDownload = await event;
      const pdfPath = path.join(output, 'face-circle-' + inches + '.pdf');
      await sizedDownload.saveAs(pdfPath);
      const pdf = await PDFDocument.load(await fs.readFile(pdfPath));
      assert.equal(pdf.getPageCount(), inches === 8 ? 2 : 1);
      pdf.getPages().forEach(p => assert.deepEqual(p.getSize(), { width: 612, height: 792 }));
      await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
      const previewData = await page.locator('#facePagePreview').evaluate(c => c.toDataURL().split(',')[1]);
      await fs.writeFile(path.join(output, 'preview-' + inches + '.png'), Buffer.from(previewData, 'base64'));
    }
    await page.locator('#faceSize').fill('3');
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
      const previewBox = await page.locator('#facePagePreview').boundingBox();
      assert.ok(previewBox.x >= 0 && previewBox.x + previewBox.width <= viewport.width, 'Page preview fits mobile viewport');
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
    // Seven 3-inch circles fill one six-photo page, then a centered final photo.
    await page.locator('#faceFiles').setInputFiles(Array.from({ length: 5 }, (_, i) => ({ ...upload[i % 2], name: 'extra-' + i + '.png' })));
    await page.waitForFunction(() => document.querySelector('#faceThumbnails').children.length === 7 && !document.querySelector('#faceExport').disabled);
    await page.locator('#faceThumbnails button').last().click();
    await page.waitForFunction(() => document.querySelector('#faceCounter').textContent === '7 / 7' && !document.querySelector('#faceExport').disabled);
    assert.ok((await page.locator('#facePageSummary').innerText()).includes('6 per page · 0.5-inch gaps · Page 2 of 2'));
    const packedEvent = page.waitForEvent('download');
    await page.locator('#faceExport').click();
    await (await packedEvent).saveAs(path.join(output, 'face-circle-packed.pdf'));
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    const packed = await PDFDocument.load(await fs.readFile(path.join(output, 'face-circle-packed.pdf')));
    assert.equal(packed.getPageCount(), 2);
    await page.locator('#faceThumbnails button').first().click();
    await page.waitForFunction(() => !document.querySelector('#faceExport').disabled);
    assert.ok((await page.locator('#facePageSummary').innerText()).includes('Page 1 of 2'));
    const packedPreview = await page.locator('#facePagePreview').evaluate(c => c.toDataURL().split(',')[1]);
    await fs.writeFile(path.join(output, 'preview-packed.png'), Buffer.from(packedPreview, 'base64'));
    await page.setViewportSize({ width: 1280, height: 1100 });
    await page.screenshot({ path: path.join(output, 'packed-desktop.png'), fullPage: true });
    await page.locator('#faceClear').click();
    assert.equal(await page.locator('#faceExport').isDisabled(), true);
    assert.equal(await page.locator('#faceThumbnails button').count(), 0);
    for (const name of ['planner', 'activity-descriptor', 'grid', 'grid-print', 'face-circle']) {
      await page.locator('[data-app-tab="' + name + '"]').click();
      assert.equal(await page.locator('[data-app-view="' + name + '"]').isVisible(), true);
    }
    assert.deepEqual(errors, []);
    console.log('PASS: selection, drag, zoom, crop persistence, keyboard, page preview, size slider, minimum/fractional/maximum size exports, reset, invalid input, add/remove, mobile, touch, clear, and all five tabs.');
    console.log('Artifacts: ' + output);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
