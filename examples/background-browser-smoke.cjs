// Offline smoke check only. No network, accounts, user profile or clicks.
// Requires Playwright and its Chromium binary in the caller's environment.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const channel = process.env.AMM_BROWSER_CHANNEL;
  if (channel && !['chrome', 'msedge'].includes(channel)) {
    throw new Error('AMM_BROWSER_CHANNEL must be chrome or msedge, or left unset for bundled Chromium.');
  }
  const browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) });
  try {
    const context = await browser.newContext();
    // Refuse external requests even if this example is extended accidentally.
    await context.route('**/*', (route) => route.abort());
    const page = await context.newPage();
    await page.setContent('<title>Offline background smoke check</title><main><h1>Ready</h1></main>');
    const actual = await page.locator('h1').innerText();
    assert.equal(actual, 'Ready');
    console.log(JSON.stringify({ status: 'passed', headless: true, fixture: 'offline', heading: actual }));
    await context.close();
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
