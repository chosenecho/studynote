// Accessibility sweep: axe-core over the template sample, light/dark, desktop/mobile.
// Run: node tools/checks/a11y.mjs [dist] [outDir]
// Exits non-zero when any critical/serious violation is found, so it can gate CI.
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
  {name: 'desktop', width: 1280, height: 900},
  {name: 'mobile', width: 390, height: 844},
];
const THEMES = ['light', 'dark'];

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

const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');
const browser = await chromium.launch({headless: true});
const report = {
  measured_at: new Date().toISOString(),
  browser: browser.version(),
  axe: JSON.parse(fs.readFileSync('node_modules/axe-core/package.json', 'utf8')).version,
  scope: 'axe-core wcag2a/wcag2aa/wcag21aa/wcag22aa/best-practice; template sample, light+dark, 1280+390.',
  pages: PAGES.map(([id, url]) => ({id, url})),
  scans: [],
  summary: {},
};

const totals = {violations: {}, incomplete: 0, passes: 0};

try {
  for (const [id, url] of PAGES) {
    for (const theme of THEMES) {
      for (const vp of VIEWPORTS) {
        const context = await browser.newContext({viewport: {width: vp.width, height: vp.height},
          colorScheme: theme, reducedMotion: 'reduce'});
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(String(e)));
        const response = await page.goto(base + url, {waitUntil: 'networkidle'});
        if (response && response.status() !== 200) errors.push('HTTP ' + response.status());
        await page.addScriptTag({content: axeSource});
        const result = await page.evaluate(async () => {
          const r = await window.axe.run(document, {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']},
            resultTypes: ['violations', 'incomplete'],
          });
          return {
            violations: r.violations.map(v => ({
              id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl, tags: v.tags,
              nodes: v.nodes.slice(0, 6).map(n => ({target: n.target, html: n.html.slice(0, 220),
                failureSummary: (n.failureSummary || '').split('\n').slice(0, 3).join(' | ')})),
              nodeCount: v.nodes.length,
            })),
            incompleteCount: r.incomplete.length,
          };
        });
        const shot = `${id}-${theme}-${vp.name}.png`;
        await page.screenshot({path: path.join(out, shot), fullPage: vp.name === 'desktop',
          animations: 'disabled'});
        for (const v of result.violations) {
          const key = v.id;
          totals.violations[key] = totals.violations[key] || {id: v.id, impact: v.impact, help: v.help,
            helpUrl: v.helpUrl, pages: new Set(), nodes: 0};
          totals.violations[key].pages.add(id);
          totals.violations[key].nodes += v.nodeCount;
        }
        totals.incomplete += result.incompleteCount;
        report.scans.push({page: id, theme, viewport: vp.name, violations: result.violations,
          incomplete: result.incompleteCount, errors, screenshot: shot});
        await context.close();
      }
    }
    process.stdout.write('.');
  }
} finally {
  await browser.close();
  server.close();
}

// Persist raw scans first: a summary-side bug must not throw away a finished sweep.
fs.writeFileSync(path.join(out, 'a11y-scans.json'), JSON.stringify(report.scans, null, 2) + '\n');

const severity = ['critical', 'serious', 'moderate', 'minor'];
report.summary = {
  scans: report.scans.length,
  byImpact: severity.reduce((acc, s) => {
    acc[s] = report.scans.reduce((n, sc) => n + sc.violations.filter(v => v.impact === s).length, 0);
    return acc;
  }, {}),
  rules: Object.values(totals.violations)
    .map(v => ({...v, pages: [...v.pages].sort()}))
    .sort((a, b) => severity.indexOf(a.impact) - severity.indexOf(b.impact) || b.nodes - a.nodes),
  incomplete: totals.incomplete,
  pageErrors: [...new Set(report.scans.flatMap(s => s.errors))],
};
fs.writeFileSync(path.join(out, 'a11y.json'), JSON.stringify(report, null, 2) + '\n');

const blocking = report.summary.byImpact.critical + report.summary.byImpact.serious;
console.log('\na11y: ' + report.scans.length + ' scans, ' + JSON.stringify(report.summary.byImpact));
for (const r of report.summary.rules.slice(0, 12)) {
  console.log(`  [${r.impact}] ${r.id} — ${r.nodes} node(s) on ${r.pages.join(',')}`);
}
if (report.summary.pageErrors.length) console.log('  page errors:', report.summary.pageErrors);
process.exit(blocking ? 1 : 0);
