import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const template = readFileSync('theme/main.html', 'utf8');
const script = template.match(/<script\b[^>]*src="https:\/\/cloud\.umami\.is\/script\.js"[^>]*>/g) ?? [];
assert.equal(script.length, 1);
for (const attribute of ['defer', 'fetchpriority="low"', 'data-website-id="7f9c831b-564f-4de7-836b-90ec5e8c8da2"', 'data-domains="studynote.chosenecho.top"', 'data-exclude-search="true"', 'data-exclude-hash="true"']) {
  assert.ok(script[0].includes(attribute), attribute);
}
const edge = JSON.parse(readFileSync('config/esa-site.json', 'utf8'));
const csp = edge.responseRules.find(rule => rule.RuleName === 'study-security').headers['Content-Security-Policy'];
const nginx = readFileSync('tools/deploy/nginx-site.conf', 'utf8');
for (const policy of [csp, nginx]) {
  assert.ok(policy.includes("script-src 'self' 'unsafe-inline' https://cloud.umami.is;"));
  assert.ok(policy.includes("connect-src 'self' https://gateway.umami.is;"));
}
console.log('Analytics configuration: tracker, production domain, URL minimization and both CSP layers passed.');
