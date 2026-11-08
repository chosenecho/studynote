import {isDeepStrictEqual} from 'node:util';

const matches = (actual, desired) => Object.entries(desired).every(([key, value]) => isDeepStrictEqual(actual?.[key], value));

// Manage only explicitly named, existing WAF rules; preserve unrelated options.
export async function syncWafRules({call, siteId, rules, apply, log = console.log}) {
  for (const {Phase, Config} of rules) {
    const list = await call('ListWafRules', {SiteId: siteId, Phase, PageNumber: 1, PageSize: 100});
    if (Number(list.TotalCount || 0) > 100) throw new Error('Managed WAF lookup exceeds one page.');
    const found = (list.Rules || []).filter(rule => rule.Name === Config.Name);
    if (found.length !== 1) throw new Error('Expected exactly one managed WAF rule: ' + Config.Name);
    const Id = found[0].Id;
    const current = await call('GetWafRule', {SiteId: siteId, Id});
    if (current.Phase !== Phase || current.Config?.Name !== Config.Name) throw new Error('Unexpected managed WAF rule: ' + Config.Name);
    if (current.Status === Config.Status && matches(current.Config, Config)) {
      log('Unchanged: ' + Config.Name);
      continue;
    }
    log((apply ? 'Update: ' : 'Would update: ') + Config.Name);
    if (!apply) continue;
    await call('UpdateWafRule', {SiteId: siteId, Id, Status: Config.Status, Config: {...current.Config, ...Config}});
    const actual = await call('GetWafRule', {SiteId: siteId, Id});
    if (actual.Phase !== Phase || actual.Status !== Config.Status || !matches(actual.Config, Config)) {
      throw new Error('WAF read-back mismatch: ' + Config.Name);
    }
  }
}
