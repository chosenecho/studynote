// Layout probe: horizontal overflow and clipping across the documented breakpoints.
// Run: node tests/browser/layout.test.mjs [dist] [outDir]
// Fails when any sampled page scrolls horizontally at 320/390/768/1280.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {chromium} from 'playwright';

const root = path.resolve(process.argv[2] || 'dist');
const out = path.resolve(process.argv[3] || 'artifacts/eval/uiux');
fs.mkdirSync(out, {recursive: true});

const PAGES = [
  ['P01', '/'],
  ['P02', '/courses/operating-systems/'],
  ['P03', '/courses/computer-networks/'],
  ['P04', '/courses/operating-systems/chapter-02/'],
  ['P05', '/courses/computer-organization/chapter-05/'],
  ['P06', '/courses/computer-networks/chapter-04/'],
  ['P07', '/courses/multimedia-technology/chapter-04/'],
  ['P08', '/courses/operating-systems/exam/03/'],
  ['P09', '/reference/'],
  ['P10', '/reference/glossary/'],
  ['P11', '/labs/scheduling/'],
  ['P12', '/labs/paging/'],
  ['P13', '/labs/quiz/'],
  ['P14', '/guide/'],
];
const VIEWPORTS = [
  {name: '320', width: 320, height: 720},
  {name: '390', width: 390, height: 844},
  {name: '768', width: 768, height: 1024},
  {name: '1280', width: 1280, height: 900},
];

const types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.txt': 'text/plain'};

const server = http.createServer((req, res) => {
  try {
    let name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (name.endsWith('/')) name += 'index.html';
    const file = path.resolve(root, '.' + name);
    if (!file.startsWith(root + path.sep)) {res.writeHead(403).end(); return;}
    if (!fs.existsSync(file)) {res.writeHead(404).end(); return;}
    res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'});
    res.end(fs.readFileSync(file));
  } catch {res.writeHead(404).end();}
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = 'http://127.0.0.1:' + server.address().port;

const browser = await chromium.launch({headless: true});
const report = {measured_at: new Date().toISOString(), browser: browser.version(),
  scope: 'Horizontal overflow at 320/390/768/1280, light palette; element-level culprits.', scans: []};
let failures = 0;

try {
  for (const [id, url] of PAGES) {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({viewport: {width: vp.width, height: vp.height}});
      const page = await context.newPage();
      await page.goto(base + url, {waitUntil: 'networkidle'});
      const result = await page.evaluate(() => {
        const docWidth = document.documentElement.clientWidth;
        const scrollWidth = document.documentElement.scrollWidth;
        const culprits = [];
        for (const el of document.querySelectorAll('body *')) {
          const style = getComputedStyle(el);
          if (style.position === 'fixed' || style.display === 'none' || style.visibility === 'hidden') continue;
          const rect = el.getBoundingClientRect();
          if (!rect.width) continue;
          // An element narrower than the viewport can still push the page when it is
          // not clipped by an ancestor; report only elements whose right edge exceeds it.
          if (rect.right > docWidth + 1) {
            culprits.push({
              tag: el.tagName.toLowerCase(),
              cls: el.className && typeof el.className === 'string' ? el.className.slice(0, 90) : '',
              id: el.id || '',
              right: Math.round(rect.right),
              width: Math.round(rect.width),
              overflowX: style.overflowX,
              text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
            });
          }
        }
        // Keep the outermost offender per subtree so a wrapper does not mask its child.
        const trimmed = culprits.filter((c, i) => !culprits.some((o, j) => j !== i && o.right >= c.right
          && o.width > c.width)).slice(0, 8);
        return {docWidth, scrollWidth, overflow: scrollWidth - docWidth, culprits: trimmed};
      });
      if (result.overflow > 1) failures++;
      report.scans.push({page: id, viewport: vp.name, ...result});
      if (result.overflow > 1) {
        await page.screenshot({path: path.join(out, `overflow-${id}-${vp.name}.png`), fullPage: true,
          animations: 'disabled'});
      }
      await context.close();
    }
    process.stdout.write('.');
  }
} finally {
  await browser.close();
  server.close();
}

fs.writeFileSync(path.join(out, 'layout.json'), JSON.stringify(report, null, 2) + '\n');
const bad = report.scans.filter(s => s.overflow > 1);
console.log('\nlayout: ' + report.scans.length + ' scans, ' + bad.length + ' overflowing');
for (const s of bad.slice(0, 20)) {
  console.log(`  ${s.page} @${s.viewport}px overflow=${s.overflow}px ` +
    s.culprits.slice(0, 3).map(c => `${c.tag}${c.cls ? '.' + c.cls.split(' ')[0] : ''}(${c.width}px)`).join(' '));
}
process.exit(failures ? 1 : 0);
