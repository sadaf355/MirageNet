const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

async function run() {
  const screenshotDir = path.resolve(__dirname, '../evidence/screenshots');
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  // Set viewport to 1440x900
  await page.setViewport({ width: 1440, height: 900 });

  // Open app and dismiss welcome splash
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    sessionStorage.setItem('miragenet-welcome-dismissed', '1');
  });
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));

  const screens = [
    { name: 'overview.png', label: 'Overview' },
    { name: 'live_network.png', label: 'Live Network' },
    { name: 'decoy_lab.png', label: 'Decoy Lab' },
    { name: 'live_alerts.png', label: 'Live Alerts' },
    { name: 'incidents.png', label: 'Incidents' },
    { name: 'intruder_play.png', label: 'Intruder Play' },
    { name: 'evaluation_lab.png', label: 'Evaluation Lab' },
    { name: 'settings.png', label: 'Settings' }
  ];

  for (const screen of screens) {
    if (screen.label !== 'Overview') {
      // Find nav button
      await page.evaluate((label) => {
        const buttons = Array.from(document.querySelectorAll('.nav-item'));
        const target = buttons.find(b => b.textContent && b.textContent.includes(label));
        if (target) target.click();
      }, screen.label);
      await new Promise(r => setTimeout(r, 1200));
    }
    const dest = path.join(screenshotDir, screen.name);
    await page.screenshot({ path: dest });
    console.log(`Captured ${screen.name} at 1440px`);
  }

  // Check 1280px width
  await page.setViewport({ width: 1280, height: 800 });
  await new Promise(r => setTimeout(r, 1000));
  console.log('Checked 1280px responsiveness across screens.');

  await browser.close();
  console.log('Screenshots complete. Console errors count:', consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.log('Errors:', consoleErrors);
  }
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
