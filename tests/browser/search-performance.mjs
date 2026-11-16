// Lab measurement of the search panel: cold open, index transfer, query latency.
// Lab numbers with CDP network/CPU emulation, not field data.
// Usage: node tests/browser/search-performance.mjs [dist|https://SITE] [out.json]
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import https from 'node:https';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import {chromium} from 'playwright';

const target = process.argv[2] || 'dist';
const remote = /^https?:\/\//.test(target);
const root = path.resolve(remote ? 'dist' : target);
const output = path.resolve(process.argv[3] || 'artifacts/search/performance.json');
const indexFile = path.join(root, 'search', 'search_index.json');
const localIndex = fs.existsSync(indexFile) ? fs.readFileSync(indexFile) : null;
const indexBrotli = localIndex && zlib.brotliCompressSync(localIndex, {
  params: {[zlib.constants.BROTLI_PARAM_QUALITY]: 11},
});

// Budgets are per device class and are regression guards, not product targets: each is
// the 2026-11-16 measurement at the shipped 1600-character cap plus the run-to-run spread
// this box produces while other jobs are running, so a change that makes search slower
// fails here while ordinary variance does not. Desktop, Brotli, 1280x900: open 757 ms,
// first query 240 ms, slowest steady query 192 ms. Mobile, Brotli, 390x844 at 1.6 Mbps
// and 4x CPU: open 2,495 ms on a quiet run and 2,805 ms with a 70% CPU neighbour, first
// query 910 ms and 1,431 ms on the same runs, slowest steady query 372 ms. The cap barely
// moves those numbers (1,200 through 1,600 all landed between 2,761 and 2,805 ms open),
// so payload is not how mobile gets faster: 1,550 ms of that open is transfer, and the
// edge serving gzip instead of Brotli adds another 434 ms. A single number for both
// classes either fails the phone or says nothing about the desktop.
const budget = {
  index_brotli_bytes: 300_000,
  desktop: {open_ms: 900, first_query_ms: 400, query_ms: 300},
  mobile: {open_ms: 3_000, first_query_ms: 1_800, query_ms: 700},
  fallback_ms: 700,
};
// The lab machine also runs builds, checks and training jobs, so a contended run can
// only ever add time. The median stays the reported figure; the minimum is recorded as
// the contention-free estimate, and a min well under the median means the box was busy
// rather than the page being slow. Raise SEARCH_RUNS when the machine is not quiet.
const runs = Number(process.env.SEARCH_RUNS || 3);
// Local mode can serve the index as Brotli (best case) or gzip, which is what the
// production edge negotiates for browser requests.
const localEncoding = process.env.SEARCH_ENCODING === 'gzip' ? 'gzip' : 'br';
const indexGzip = localIndex && zlib.gzipSync(localIndex, {level: 9});

const queries = [
  {q: '抖动', expect: 'courses/operating-systems'},
  {q: '子网', expect: 'courses/computer-networks'},
  {q: '页面置换', expect: 'courses/operating-systems'},
  {q: 'Cache', expect: null},
  {q: '死锁', expect: 'courses/operating-systems'},
  {q: 'FCFS', expect: 'labs/scheduling'},
  {q: '阿基米德', expect: null},
  {q: 'zzzzzz', expect: null},
];
const devices = [
  {name: 'desktop', viewport: {width: 1280, height: 900}, latency: 40, download: 10_000_000 / 8, cpu: 1},
  {name: 'mobile', viewport: {width: 390, height: 844}, latency: 150, download: 1_600_000 / 8, cpu: 4},
];
const types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.json': 'application/json'};

const server = http.createServer((req, res) => {
  let name = '';
  try {
    name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (name.endsWith('/')) name += 'index.html';
    const file = path.resolve(root, '.' + name);
    if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
    const body = file === indexFile && indexBrotli
      ? (localEncoding === 'gzip' ? indexGzip : indexBrotli)
      : fs.readFileSync(file);
    const headers = {'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store'};
    if (indexBrotli && body !== undefined && file === indexFile) headers['Content-Encoding'] = localEncoding;
    res.writeHead(200, {...headers, 'Content-Length': body.length});
    res.end(body);
  } catch {
    if (!res.headersSent) res.writeHead(404).end();
    else console.log('missing during measurement:', name);
  }
});

// Report the index the measured site actually serves, plus the build in dist/.
async function servedIndex() {
  if (!remote) {
    return {source: 'dist', docs: null, raw_bytes: localIndex.length, brotli_bytes: indexBrotli.length,
      gzip_bytes: indexGzip.length, encoding: localEncoding,
      sha256: crypto.createHash('sha256').update(localIndex).digest('hex').slice(0, 16),
      built_at: fs.statSync(indexFile).mtime.toISOString()};
  }
  return new Promise((resolve, reject) => {
    https.get(target.replace(/\/$/, '') + '/search/search_index.json',
      {headers: {accept: 'application/json', 'accept-encoding': 'br, gzip'}}, res => {
        const chunks = [];
        res.on('data', chunk => chunks.push(chunk));
        res.on('end', () => {
          let body = Buffer.concat(chunks);
          const encoding = res.headers['content-encoding'];
          if (encoding === 'br') body = zlib.brotliDecompressSync(body);
          else if (encoding === 'gzip') body = zlib.gunzipSync(body);
          const data = JSON.parse(body.toString('utf8'));
          resolve({source: 'live', docs: data.docs.length, raw_bytes: body.length,
            transfer_bytes: +res.headers['content-length'] || Buffer.concat(chunks).length,
            encoding: encoding || 'identity', last_modified: res.headers['last-modified'],
            text_chars: data.docs.reduce((sum, doc) => sum + doc.text.length, 0),
            sha256: crypto.createHash('sha256').update(body).digest('hex').slice(0, 16)});
        });
      }).on('error', reject);
  });
}

const browser = await chromium.launch({headless: true});

async function measureQuery(page, q) {
  return page.evaluate(async q => {
    const input = document.querySelector('.md-search__input');
    const meta = document.querySelector('.md-search-result__meta');
    const list = document.getElementById('study-search-results');
    const settled = () => {
      const text = meta.textContent;
      const done = /\d+ 个符合条件/.test(text) || text.includes('没有找到');
      if (!done) return false;
      const links = [...list.querySelectorAll('.md-search-result__link')];
      return links.length ? links.some(a => new URL(a.href).searchParams.get('h') === q) : true;
    };
    input.focus();
    if (input.value) {
      input.value = '';
      input.dispatchEvent(new Event('input', {bubbles: true}));
    }
    await new Promise(resolve => {
      const tick = () => (!list.children.length && meta.textContent === '输入章节名或概念开始搜索')
        ? resolve() : requestAnimationFrame(tick);
      tick();
    });
    const t0 = performance.now();
    input.value = q;
    input.dispatchEvent(new Event('input', {bubbles: true}));
    await new Promise(resolve => {
      const deadline = performance.now() + 6000;
      const tick = () => settled() || performance.now() > deadline
        ? resolve() : requestAnimationFrame(tick);
      tick();
    });
    const ms = performance.now() - t0;
    const links = [...list.querySelectorAll('.md-search-result__link')];
    // The input handler waits 150 ms before querying; report the kernel cost too.
    return {query: q, ms, kernel_ms: +Math.max(0, ms - 150).toFixed(1), meta: meta.textContent,
      count: links.length, top3: links.slice(0, 3).map(a => new URL(a.href).pathname)};
  }, q);
}

const report = {
  measured_at: new Date().toISOString(), browser: browser.version(), runs_per_device: runs,
  mode: remote ? 'live' : 'dist', target: remote ? target : 'dist',
  scope: 'Local cold-context lab measurement, CDP network/CPU emulation; no field data.',
  index: {}, budget, devices, samples: [],
};
try {
  if (!remote) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = remote ? target.replace(/\/$/, '') : 'http://127.0.0.1:' + server.address().port;
  report.index = await servedIndex();
  if (localIndex) report.index.local_build = {docs: JSON.parse(localIndex.toString('utf8')).docs.length,
    raw_bytes: localIndex.length, brotli_bytes: indexBrotli.length};

  for (const device of devices) for (let run = 1; run <= runs; run++) {
    const context = await browser.newContext({viewport: device.viewport});
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', {offline: false, latency: device.latency,
      downloadThroughput: device.download, uploadThroughput: 750_000 / 8});
    await cdp.send('Emulation.setCPUThrottlingRate', {rate: device.cpu});
    await page.goto(base + '/', {waitUntil: 'networkidle', timeout: 60_000});

    const open = await page.evaluate(async () => {
      const rootEl = document.querySelector('[data-study-search]');
      const meta = rootEl.querySelector('.md-search-result__meta');
      const seen = [];
      new MutationObserver(() => seen.push({at: performance.now(), text: meta.textContent}))
        .observe(meta, {childList: true, characterData: true, subtree: true});      const idle = () => meta.textContent === '输入章节名或概念开始搜索' && !rootEl.hasAttribute('aria-busy');
      const t0 = performance.now();
      document.querySelector('.md-search__input').focus();
      if (!document.querySelector('#__search').checked) {
        // Desktop opens from the magnifier field, mobile from the header button;
        // both run the same handler, so the measured path matches the device.
        document.querySelector('[data-search-toggle]').click();
      }
      await new Promise(resolve => {
        const deadline = performance.now() + 8000;
        const tick = () => (idle() && seen.some(s => s.text.includes('正在加载'))) || performance.now() > deadline
          ? resolve() : requestAnimationFrame(tick);
        tick();
      });
      const ready = idle() && seen.some(s => s.text.includes('正在加载'));
      const readyAt = performance.now();
      const entry = performance.getEntriesByType('resource').find(r => r.name.includes('search_index.json'));
      return {
        ready, open_ms: readyAt - t0,
        states: seen.map(s => s.text),
        fetch: entry && {start_ms: entry.startTime, end_ms: entry.responseEnd, duration_ms: entry.duration,
          transfer_bytes: entry.transferSize, decoded_bytes: entry.decodedBodySize},
        // The loader shows the retry control only when it gives up; the same block
        // carries just the fallback links when a query simply has no results.
        failed: (() => {
          const recovery = rootEl.querySelector('[data-search-recovery]');
          const retry = rootEl.querySelector('.search-retry');
          return !recovery.hidden && !retry.hidden;
        })(),
      };
    });

    // The first query also pays the worker's one-time warm-up; measure it separately
    // so steady-state numbers below are not taken from a cold kernel.
    if (!open.ready) {
      const indexRequests = 0;
      report.samples.push({device: device.name, run, ...open, index_requests: indexRequests,
        queries: [], error: 'search did not become ready'});
      await context.close();
      continue;
    }
    const firstQuery = await measureQuery(page, '进程');
    const firstQueryRepeat = await measureQuery(page, '进程');
    const results = [];
    for (const item of queries) {
      const result = await measureQuery(page, item.q);
      // Record whether the expected section ranks in the first three results.
      result.matches_expectation = item.expect
        ? result.top3.some(href => href.startsWith('/' + item.expect)) : null;
      results.push(result);
    }

    const median = values => {
      const sorted = [...values].sort((a, b) => a - b);
      return +sorted[Math.floor(sorted.length / 2)].toFixed(1);
    };
    const queryMs = {};
    for (const r of results) (queryMs[r.query] ??= []).push(r.ms);
    const indexRequests = await page.evaluate(() => performance.getEntriesByType('resource')
      .filter(r => r.name.includes('search_index.json')).length);
    report.samples.push({device: device.name, run, ...open, index_requests: indexRequests,
      first_query: firstQuery, first_query_repeat: firstQueryRepeat, queries: results,
      median_query_ms: Object.fromEntries(Object.entries(queryMs).map(([q, v]) => [q, median(v)])),
      max_query_ms: +Math.max(...results.map(r => r.ms)).toFixed(1)});
    await context.close();
  }

  const summarize = samples => {
    const opens = samples.map(s => s.open_ms);
    const fetch = samples.map(s => s.fetch?.duration_ms).filter(Boolean);
    const measured = samples.filter(s => s.first_query);
    const median = values => {
      const sorted = [...values].sort((a, b) => a - b);
      return +sorted[Math.floor(sorted.length / 2)].toFixed(1);
    };
    const perQuery = {};
    for (const s of measured) for (const r of s.queries) (perQuery[r.query] ??= []).push(r.ms);
    const min = values => values.length ? +Math.min(...values).toFixed(1) : null;
    const parse = samples.map(s => s.open_ms - (s.fetch?.duration_ms || 0));
    return {
      open_ms: median(opens), open_ms_runs: opens.map(v => +v.toFixed(1)),
      open_ms_min: min(opens),
      fetch_ms: median(fetch), fetch_ms_min: min(fetch), index_transfer_bytes: samples[0].fetch?.transfer_bytes ?? 0,
      parse_and_worker_ms: median(parse), parse_and_worker_ms_min: min(parse),
      first_query_ms: measured.length ? median(measured.map(s => s.first_query.ms)) : null,
      first_query_kernel_ms: measured.length ? median(measured.map(s => s.first_query.kernel_ms)) : null,
      first_query_repeat_ms: measured.length ? median(measured.map(s => s.first_query_repeat.ms)) : null,
      query_ms: Object.fromEntries(Object.entries(perQuery).map(([q, v]) => [q, median(v)])),
      max_query_ms: measured.length ? median(measured.map(s => s.max_query_ms)) : null,
      max_sample_ms: measured.length ? +Math.max(...measured.flatMap(s => s.queries.map(r => r.ms))).toFixed(1) : null,
      index_requests: [...new Set(samples.map(s => s.index_requests))],
      ready_failures: samples.filter(s => s.error).length,
      zero_result_queries: samples[0].queries.filter(r => !r.count).map(r => r.query),
    };
  };
  report.summary = Object.fromEntries(devices.map(d => [d.name, summarize(
    report.samples.filter(s => s.device === d.name))]));

  const verdicts = [];
  for (const [name, s] of Object.entries(report.summary)) {
    const limit = budget[name];
    verdicts.push({check: `${name} index transfer ≤ ${budget.index_brotli_bytes} B`, value: s.index_transfer_bytes, pass: s.index_transfer_bytes <= budget.index_brotli_bytes});
    verdicts.push({check: `${name} index fetched once`, value: s.index_requests, pass: s.index_requests.length === 1 && s.index_requests[0] === 1});
    verdicts.push({check: `${name} open ≤ ${limit.open_ms} ms`, value: s.open_ms, pass: s.open_ms <= limit.open_ms});
    verdicts.push({check: `${name} search ready`, value: s.ready_failures + ' failures', pass: s.ready_failures === 0});
    if (s.first_query_ms !== null) {
      verdicts.push({check: `${name} first query ≤ ${limit.first_query_ms} ms`, value: s.first_query_ms, pass: s.first_query_ms <= limit.first_query_ms});
      const worst = Math.max(...Object.values(s.query_ms));
      verdicts.push({check: `${name} slowest steady query ≤ ${limit.query_ms} ms`, value: +worst.toFixed(1), pass: worst <= limit.query_ms});
    }
  }
  const fallback = Math.max(...report.samples.flatMap(s => s.queries.filter(r => !r.count).map(r => r.ms)));
  verdicts.push({check: `zero-result/rescue ≤ ${budget.fallback_ms} ms`, value: +fallback.toFixed(1), pass: fallback <= budget.fallback_ms});
  const wrong = report.samples.flatMap(s => s.queries).filter(r => r.matches_expectation === false);
  verdicts.push({check: 'expected section ranks in top three', value: wrong.length ? wrong.map(r => r.query) : 'all matched', pass: wrong.length === 0});
  verdicts.push({check: 'no load failure or watchdog trip', value: report.samples.filter(s => s.failed).length + ' failures', pass: report.samples.every(s => !s.failed)});
  report.verdict = {pass: verdicts.every(v => v.pass), checks: verdicts};

  fs.mkdirSync(path.dirname(output), {recursive: true});
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({output, samples: report.samples.length, index: report.index,
    summary: report.summary, verdict: report.verdict}, null, 2));
} finally {
  await browser.close();
  if (!remote) await new Promise(resolve => server.close(resolve));
}
