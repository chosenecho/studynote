import assert from 'node:assert/strict';
import test from 'node:test';
import {syncWafRules} from '../../tools/deploy/esa-waf.mjs';

const desired = {Name: 'study-asset-hotlink', Type: 'http_custom', Status: 'on', Action: 'deny', Expression: 'expanded course figures'};

function fixture({config = {...desired, Expression: 'original course figures'}, names = [desired.Name], ignoreUpdate = false} = {}) {
  let current = {Id: 42, Phase: 'http_custom', Status: 'on', Config: {...config, Description: 'preserve this option'}};
  const calls = [];
  const messages = [];
  const call = async (action, args) => {
    calls.push({action, args: structuredClone(args)});
    assert.equal(args.SiteId, 123);
    if (action === 'ListWafRules') return {TotalCount: names.length, Rules: names.map((Name, index) => ({Name, Id: 42 + index}))};
    assert.equal(args.Id, 42, 'only the named rule may be accessed');
    if (action === 'GetWafRule') return structuredClone(current);
    assert.equal(action, 'UpdateWafRule');
    if (!ignoreUpdate) current = {...current, Status: args.Status, Config: structuredClone(args.Config)};
    return {};
  };
  return {
    calls,
    messages,
    run: apply => syncWafRules({call, siteId: 123, rules: [{Phase: 'http_custom', Config: desired}], apply, log: message => messages.push(message)}),
  };
}

test('preview reports drift without writing', async () => {
  const f = fixture();
  await f.run(false);
  assert(!f.calls.some(({action}) => action === 'UpdateWafRule'));
  assert.deepEqual(f.messages, ['Would update: study-asset-hotlink']);
});

test('matching rule remains unchanged even when applying', async () => {
  const f = fixture({config: desired});
  await f.run(true);
  assert(!f.calls.some(({action}) => action === 'UpdateWafRule'));
  assert.deepEqual(f.messages, ['Unchanged: study-asset-hotlink']);
});

test('apply preserves unowned options and does not touch other rules', async () => {
  const f = fixture({names: [desired.Name, 'study-block-scanners']});
  await f.run(true);
  const updates = f.calls.filter(({action}) => action === 'UpdateWafRule');
  assert.equal(updates.length, 1);
  assert.deepEqual(updates[0].args, {SiteId: 123, Id: 42, Status: 'on', Config: {...desired, Description: 'preserve this option'}});
  assert.equal(f.calls.filter(({action}) => action === 'GetWafRule').length, 2, 'read back the applied rule');
});

test('missing or ambiguous managed rule fails before writing', async () => {
  for (const names of [[], [desired.Name, desired.Name]]) {
    const f = fixture({names});
    await assert.rejects(f.run(true), /Expected exactly one managed WAF rule/);
    assert(!f.calls.some(({action}) => action === 'UpdateWafRule'));
  }
});

test('failed cloud read-back rejects the update', async () => {
  const f = fixture({ignoreUpdate: true});
  await assert.rejects(f.run(true), /WAF read-back mismatch/);
});
