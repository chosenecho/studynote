// The search panel must return every page whose text contains the query.
// The worker's tokenizer splits only on whitespace and punctuation, so a Chinese phrase
// reaches it as one long token: it under-matches, and it pads the list with pages that
// do not contain the query at all. `merge()` in docs/assets/javascripts/search.mjs
// repairs both halves by letting the entry text decide membership; this asserts that
// repair against the index the page actually downloaded.
// Usage: node tests/browser/search-completeness.mjs [dist|https://SITE]
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {chromium} from 'playwright';

const target = process.argv[2] || 'dist';
const remote = /^https?:\/\//.test(target);
const root = path.resolve(remote ? 'dist' : target);
const terms = ['死锁', '中断', '页表', '加密', 'SPOOLing', '索引', '抖动', '子网', 'TCP', '缓存', '帧', '调度'];
const types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.json': 'application/json'};

function page(html) {
  return String(html).replace(/<[^>]*>/g, '').toLowerCase();
}

// Same membership rule as the panel: the part appears literally, or — for a Han run of
// three or more characters — most of its adjacent pairs do.
function matches(doc, parts) {
  const content = page(doc.title) + ' ' + page(doc.text);
  return parts.every(part => {
    if (content.includes(part)) return true;
    if (!/^[\p{Script=Han}]{3,}$/u.test(part)) return false;
    const grams = [...new Set(Array.from(part).slice(1).map((char, i) => part[i] + char))];
    return grams.filter(gram => content.includes(gram)).length >= Math.ceil(grams.length * .6);
  });
}

function truthPages(index, term) {
  const parts = term.toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
  const pages = new Set();
  for (const doc of index.docs) if (matches(doc, parts)) pages.add((doc.location || '').split('#')[0]);
  return pages;
}

const server = http.createServer((req, res) => {
  let name = '';
  try {
    name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (name.endsWith('/')) name += 'index.html';
    const file = path.resolve(root, '.' + name);
    if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
    const body = fs.readFileSync(file);
    res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-store', 'Content-Length': body.length});
    res.end(body);
  } catch {
    if (!res.headersSent) res.writeHead(404).end();
  }
});

const browser = await chromium.launch({headless: true});
const failures = [];
try {
  if (!remote) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = remote ? target.replace(/\/$/, '') : 'http://127.0.0.1:' + server.address().port;
  const index = JSON.parse(fs.readFileSync(path.join(root, 'search', 'search_index.json'), 'utf8'));

  const context = await browser.newContext({viewport: {width: 1280, height: 900}});
  const page_ = await context.newPage();
  await page_.goto(base + '/', {waitUntil: 'networkidle', timeout: 60_000});
  await page_.evaluate(() => {
    document.querySelector('.md-search__input').focus();
    if (!document.querySelector('#__search').checked) document.querySelector('[data-search-toggle]').click();
  });
  await page_.waitForFunction(() => {
    const meta = document.querySelector('.md-search-result__meta');
    return meta.textContent === '输入章节名或概念开始搜索'
      && !document.querySelector('[data-study-search]').hasAttribute('aria-busy');
  }, {timeout: 30_000});

  const rows = [];
  for (const term of terms) {
    const found = await page_.evaluate(async q => {
      const input = document.querySelector('.md-search__input');
      const meta = document.querySelector('.md-search-result__meta');
      const list = document.getElementById('study-search-results');
      const settled = () => {
        const text = meta.textContent;
        if (!/\d+ 个符合条件/.test(text) && !text.includes('没有找到')) return false;
        const links = [...list.querySelectorAll('.md-search-result__link')];
        return links.length ? links.some(a => new URL(a.href).searchParams.get('h') === q) : true;
      };
      input.value = q;
      input.dispatchEvent(new Event('input', {bubbles: true}));
      await new Promise(resolve => {
        const deadline = performance.now() + 8000;
        const tick = () => settled() || performance.now() > deadline ? resolve() : requestAnimationFrame(tick);
        tick();
      });
      const links = [...list.querySelectorAll('.md-search-result__link')];
      return {pages: [...new Set(links.map(a => new URL(a.href).pathname.replace(/^\//, '')))],
        count: links.length, meta: meta.textContent};
    }, term);
    const expected = truthPages(index, term);
    const missing = [...expected].filter(p => !found.pages.includes(p));
    const extra = found.pages.filter(p => !expected.has(p));
    rows.push({term, expected: expected.size, shown: found.pages.length, links: found.count, missing, extra});
    if (missing.length) failures.push(`${term}: ${missing.length} page(s) missing — ${missing.slice(0, 3).join(', ')}`);
    if (extra.length) failures.push(`${term}: ${extra.length} page(s) without the term — ${extra.slice(0, 3).join(', ')}`);
    if (!expected.size && found.count) failures.push(`${term}: results for a term the index does not contain`);
  }
  await context.close();

  const spool = rows.find(r => r.term === 'SPOOLing');
  if (!spool?.links) failures.push('SPOOLing: no results, the worker index lost the term entirely');

  console.log(JSON.stringify({mode: remote ? 'live' : 'dist', terms: rows,
    missing: rows.reduce((s, r) => s + r.missing.length, 0),
    extra: rows.reduce((s, r) => s + r.extra.length, 0)}, null, 1));
  if (failures.length) {
    console.log('\n' + failures.join('\n'));
    process.exitCode = 1;
  } else {
    console.log(`Search completeness passed: ${rows.length} terms, ${rows.reduce((s, r) => s + r.expected, 0)} pages`);
  }
} finally {
  await browser.close();
  if (!remote) await new Promise(resolve => server.close(resolve));
}
