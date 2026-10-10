'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const GATE = path.resolve(__dirname, '../npm-audit-gate.cjs');
const ADVISORY = 'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm';
const REPOSITORY = 'ProjectAppCore/base_django_react_next_feature';

function arrange(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'npm-audit-gate-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const context = {
    'eslint.config.mjs': 'export default [];\n',
    'package.json': JSON.stringify({ scripts: { lint: 'eslint' }, devDependencies: { 'eslint-config-next': '16.3.8' } }),
  };
  for (const [name, content] of Object.entries(context)) fs.writeFileSync(path.join(directory, name), content);

  const packages = {
    'eslint-config-next': { version: '16.3.8', node: 'node_modules/eslint-config-next', via: '@next/eslint-plugin-next' },
    '@next/eslint-plugin-next': { version: '16.3.8', node: 'node_modules/@next/eslint-plugin-next', via: 'fast-glob' },
    'fast-glob': { version: '3.3.1', node: 'node_modules/fast-glob', via: 'micromatch' },
    micromatch: { version: '4.0.8', node: 'node_modules/micromatch', via: 'braces' },
    braces: { version: '3.0.3', node: 'node_modules/braces' },
  };
  const policy = {
    schemaVersion: 1,
    exception: {
      advisory: ADVISORY,
      repository: REPOSITORY,
      owner: 'Template security owner',
      reason: 'Reviewed ESLint configuration has no untrusted glob input',
      reviewedAt: '2026-10-10T00:00:00Z',
      expiresAt: '2026-10-24T00:00:00Z',
      packages,
      context: Object.fromEntries(Object.entries(context).map(([name, content]) => [name, createHash('sha256').update(content).digest('hex')])),
    },
  };
  const report = {
    auditReportVersion: 2,
    vulnerabilities: Object.fromEntries(Object.entries(packages).map(([name, item]) => [name, {
      name,
      severity: 'high',
      nodes: [item.node],
      via: item.via ? [item.via] : [{ name: 'braces', dependency: 'braces', severity: 'high', url: ADVISORY, range: '<=3.0.3' }],
    }])),
    metadata: { vulnerabilities: { info: 0, low: 0, moderate: 0, high: 5, critical: 0, total: 5 } },
  };
  const lock = {
    lockfileVersion: 3,
    packages: Object.fromEntries(Object.values(packages).map(item => [item.node, {
      version: item.version,
      dev: true,
      dependencies: item.via ? { [item.via]: packages[item.via].version } : {},
    }])),
  };
  const clock = path.join(directory, 'clock.cjs');
  fs.writeFileSync(clock, 'Date.now = () => Date.parse("2026-10-10T12:00:00Z");\n');
  const environment = { ...process.env, GITHUB_REPOSITORY: REPOSITORY };
  const run = (reportText = JSON.stringify(report)) => {
    fs.writeFileSync(path.join(directory, 'report.json'), reportText);
    fs.writeFileSync(path.join(directory, 'lock.json'), JSON.stringify(lock));
    fs.writeFileSync(path.join(directory, 'policy.json'), JSON.stringify(policy));
    return spawnSync(process.execPath, ['--require', clock, GATE, path.join(directory, 'report.json'), path.join(directory, 'lock.json'), path.join(directory, 'policy.json'), directory], { encoding: 'utf8', env: environment });
  };
  return { directory, clock, report, lock, policy, environment, run };
}

test('allows the reviewed dev exception with an explicit warning', t => {
  const fixture = arrange(t);

  const result = fixture.run();

  assert.equal(result.status, 0);
  assert.match(result.stderr, /TEMPORARY SECURITY EXCEPTION: https:\/\/github.com\/advisories\/GHSA-vfj7-8cjw-p6xm/);
  assert.match(result.stderr, /owner=Template security owner; reason=Reviewed ESLint configuration has no untrusted glob input; expires=2026-10-24T00:00:00Z/);
});

test('allows a clean audit after the exception expires', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities = {};
  fixture.report.metadata.vulnerabilities.high = 0;
  fixture.report.metadata.vulnerabilities.total = 0;
  delete fixture.environment.GITHUB_REPOSITORY;
  fs.writeFileSync(fixture.clock, 'Date.now = () => Date.parse("2026-10-25T00:00:00Z");\n');

  const result = fixture.run();

  assert.equal(result.status, 0);
  assert.match(result.stdout, /No high\/critical advisories; no exception used/);
  assert.equal(result.stderr, '');
});

test('rejects the exception at its exact expiration boundary', t => {
  const fixture = arrange(t);
  fs.writeFileSync(fixture.clock, 'Date.now = () => Date.parse("2026-10-24T00:00:00Z");\n');

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exception expired at 2026-10-24T00:00:00Z/);
});

test('rejects an automatically extended expiration', t => {
  const fixture = arrange(t);
  fixture.policy.exception.expiresAt = '2026-11-07T00:00:00Z';

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exception must expire at 2026-10-24T00:00:00Z/);
});

test('rejects another advisory on braces', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities.braces.via[0].url = 'https://github.com/advisories/GHSA-grv7-fg5c-xmjg';

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unexpected braces advisory/);
});

test('rejects a new high vulnerability outside the reviewed chain', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities.axios = { name: 'axios', severity: 'high', nodes: ['node_modules/axios'], via: [{ url: 'https://github.com/advisories/new-advisory' }] };
  fixture.report.metadata.vulnerabilities.high = 6;
  fixture.report.metadata.vulnerabilities.total = 6;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Only the exact reviewed five-package chain/);
});

test('rejects a critical finding in the reviewed chain', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities.braces.severity = 'critical';
  fixture.report.metadata.vulnerabilities.high = 4;
  fixture.report.metadata.vulnerabilities.critical = 1;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Critical advisories remain blocking/);
});

test('rejects a reviewed package that becomes a runtime dependency', t => {
  const fixture = arrange(t);
  fixture.lock.packages['node_modules/braces'].dev = false;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exception must remain dev-only: braces/);
});

test('rejects a changed upstream package version', t => {
  const fixture = arrange(t);
  fixture.lock.packages['node_modules/fast-glob'].version = '3.3.3';

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Locked version changed: fast-glob/);
});

test('rejects an unreviewed package installation path', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities.braces.nodes = ['node_modules/other/node_modules/braces'];

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Finding node changed: braces/);
});

test('rejects a shortcut in the vulnerability chain', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities['eslint-config-next'].via = ['braces'];

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Finding dependency edge changed: eslint-config-next/);
});

test('rejects an incomplete exception chain', t => {
  const fixture = arrange(t);
  delete fixture.report.vulnerabilities.micromatch;
  fixture.report.metadata.vulnerabilities.high = 4;
  fixture.report.metadata.vulnerabilities.total = 4;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Only the exact reviewed five-package chain/);
});

test('rejects a changed ESLint configuration fingerprint', t => {
  const fixture = arrange(t);
  fs.writeFileSync(path.join(fixture.directory, 'eslint.config.mjs'), 'export default [{ settings: { next: { rootDir: process.env.UNTRUSTED_GLOB } } }];\n');

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Reviewed ESLint context changed: eslint.config.mjs/);
});

test('rejects an exception copied to a derived repository', t => {
  const fixture = arrange(t);
  fixture.environment.GITHUB_REPOSITORY = 'ProjectAppCore/customer-project';

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exception requires the original GITHUB_REPOSITORY identity/);
});

test('rejects an exception without repository identity', t => {
  const fixture = arrange(t);
  delete fixture.environment.GITHUB_REPOSITORY;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exception requires the original GITHUB_REPOSITORY identity/);
});

test('rejects an npm audit error response', t => {
  const fixture = arrange(t);
  fixture.report.error = { code: 'ENOTFOUND', summary: 'Registry unavailable' };

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Audit returned an error/);
});

test('rejects invalid audit JSON', t => {
  const fixture = arrange(t);

  const result = fixture.run('{ invalid');

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Cannot read JSON .*report.json/);
});

test('rejects an array instead of the vulnerability map', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities = [];

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Audit vulnerabilities must be an object/);
});

test('rejects an unknown vulnerability severity', t => {
  const fixture = arrange(t);
  fixture.report.vulnerabilities.braces.severity = 'unclassified';

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown severity: braces/);
});

test('rejects inconsistent audit totals', t => {
  const fixture = arrange(t);
  fixture.report.metadata.vulnerabilities.total = 0;

  const result = fixture.run();

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Inconsistent audit total/);
});
