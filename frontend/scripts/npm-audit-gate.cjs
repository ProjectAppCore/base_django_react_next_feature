'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const ADVISORY = 'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm';
const REPOSITORY = 'ProjectAppCore/base_django_react_next_feature';
const EXPIRES_AT = '2026-10-24T00:00:00Z';
const CONTEXT_FILES = ['eslint.config.mjs', 'package.json'];
const PACKAGES = {
  'eslint-config-next': { version: '16.3.8', via: '@next/eslint-plugin-next' },
  '@next/eslint-plugin-next': { version: '16.3.8', via: 'fast-glob' },
  'fast-glob': { version: '3.3.1', via: 'micromatch' },
  micromatch: { version: '4.0.8', via: 'braces' },
  braces: { version: '3.0.3' },
};
const SEVERITIES = ['info', 'low', 'moderate', 'high', 'critical'];

function requireObject(value, label) {
  assert.ok(value !== null && typeof value === 'object' && !Array.isArray(value), `${label} must be an object`);
}

function requireKeys(value, keys, label) {
  requireObject(value, label);
  assert.deepEqual(Object.keys(value).sort(), [...keys].sort(), `${label} fields changed`);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    throw new Error(`Cannot read JSON ${file}: ${error.message}`);
  }
}

function blockingFindings(report) {
  requireObject(report, 'Audit report');
  assert.equal(report.auditReportVersion, 2, 'Unsupported audit report version');
  assert.ok(!Object.hasOwn(report, 'error'), 'Audit returned an error');
  requireObject(report.vulnerabilities, 'Audit vulnerabilities');
  requireObject(report.metadata, 'Audit metadata');
  requireKeys(report.metadata.vulnerabilities, [...SEVERITIES, 'total'], 'Audit totals');

  const counts = Object.fromEntries(SEVERITIES.map(severity => [severity, 0]));
  const blocking = [];
  for (const [name, item] of Object.entries(report.vulnerabilities)) {
    requireObject(item, `Finding ${name}`);
    assert.equal(item.name, name, `Finding name mismatch: ${name}`);
    assert.ok(SEVERITIES.includes(item.severity), `Unknown severity: ${name}`);
    assert.ok(Array.isArray(item.nodes) && item.nodes.length > 0 && item.nodes.every(node => typeof node === 'string'), `Invalid finding nodes: ${name}`);
    assert.ok(Array.isArray(item.via) && item.via.length > 0, `Invalid finding advisories: ${name}`);
    counts[item.severity] += 1;
    if (item.severity === 'high' || item.severity === 'critical') blocking.push([name, item]);
  }
  for (const severity of SEVERITIES) {
    assert.equal(report.metadata.vulnerabilities[severity], counts[severity], `Inconsistent audit ${severity} total`);
  }
  assert.equal(report.metadata.vulnerabilities.total, Object.values(counts).reduce((sum, count) => sum + count, 0), 'Inconsistent audit total');
  return blocking;
}

function validatePolicy(policy) {
  requireKeys(policy, ['schemaVersion', 'exception'], 'Policy');
  assert.equal(policy.schemaVersion, 1, 'Unsupported policy schema');
  const exception = policy.exception;
  requireKeys(exception, ['advisory', 'repository', 'owner', 'reason', 'reviewedAt', 'expiresAt', 'packages', 'context'], 'Exception');
  assert.equal(exception.advisory, ADVISORY, 'Exception advisory changed');
  assert.equal(exception.repository, REPOSITORY, 'Exception repository changed');
  for (const field of ['owner', 'reason']) {
    assert.ok(typeof exception[field] === 'string' && exception[field].trim().length > 0 && !/[\r\n]/.test(exception[field]), `Exception ${field} is required on one line`);
  }
  assert.ok(typeof exception.reviewedAt === 'string' && /^2026-10-10T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(exception.reviewedAt) && Number.isFinite(Date.parse(exception.reviewedAt)), 'Exception review must be dated 2026-10-10 UTC');
  assert.equal(exception.expiresAt, EXPIRES_AT, 'Exception must expire at 2026-10-24T00:00:00Z');
  requireKeys(exception.packages, Object.keys(PACKAGES), 'Exception packages');
  for (const [name, expected] of Object.entries(PACKAGES)) {
    assert.deepEqual(exception.packages[name], { ...expected, node: `node_modules/${name}` }, `Exception package contract changed: ${name}`);
  }
  requireKeys(exception.context, CONTEXT_FILES, 'Exception context');
  for (const file of CONTEXT_FILES) {
    assert.ok(typeof exception.context[file] === 'string' && /^[a-f0-9]{64}$/.test(exception.context[file]), `Invalid SHA-256 context fingerprint: ${file}`);
  }
  return exception;
}

function validateException(blocking, lock, exception, contextDir) {
  assert.ok(Date.now() < Date.parse(exception.expiresAt), `Exception expired at ${exception.expiresAt}; review upstream remediation`);
  assert.equal(process.env.GITHUB_REPOSITORY, exception.repository, 'Exception requires the original GITHUB_REPOSITORY identity; derived repositories need their own review');
  assert.deepEqual(blocking.map(([name]) => name).sort(), Object.keys(PACKAGES).sort(), 'Only the exact reviewed five-package chain may be excepted');
  for (const [name, item] of blocking) {
    const expected = exception.packages[name];
    assert.equal(item.severity, 'high', `Critical advisories remain blocking: ${name}`);
    assert.deepEqual(item.nodes, [expected.node], `Finding node changed: ${name}`);
    const installedNodes = Object.keys(lock.packages).filter(node => node === expected.node || node.endsWith(`/node_modules/${name}`));
    assert.deepEqual(installedNodes, [expected.node], `Installed package paths changed: ${name}`);
    const installed = lock.packages[expected.node];
    requireObject(installed, `Locked package ${name}`);
    assert.equal(installed.dev, true, `Exception must remain dev-only: ${name}`);
    assert.equal(installed.version, expected.version, `Locked version changed: ${name}`);
    if (expected.via) {
      assert.deepEqual(item.via, [expected.via], `Finding dependency edge changed: ${name}`);
      assert.ok(typeof installed.dependencies?.[expected.via] === 'string', `Locked dependency edge missing: ${name}`);
    } else {
      assert.equal(item.via.length, 1, 'Unexpected braces advisory');
      const advisory = item.via[0];
      requireObject(advisory, 'Braces advisory');
      assert.ok(advisory.name === 'braces' && advisory.dependency === 'braces' && advisory.severity === 'high' && advisory.url === ADVISORY && advisory.range === '<=3.0.3', 'Unexpected braces advisory or affected range');
    }
  }
  for (const file of CONTEXT_FILES) {
    const filename = path.join(contextDir, file);
    assert.ok(fs.lstatSync(filename).isFile(), `Reviewed context must be a regular file: ${file}`);
    const digest = createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
    assert.equal(digest, exception.context[file], `Reviewed ESLint context changed: ${file}`);
  }
}

function main() {
  try {
    assert.equal(process.argv.length, 6, 'Usage: node scripts/npm-audit-gate.cjs <report.json> <package-lock.json> <policy.json> <frontend-context-dir>');
    const [, , reportFile, lockFile, policyFile, contextDir] = process.argv;
    const report = readJson(reportFile);
    const lock = readJson(lockFile);
    const policy = readJson(policyFile);
    const blocking = blockingFindings(report);
    requireObject(lock, 'Package lock');
    assert.equal(lock.lockfileVersion, 3, 'Unsupported package lock version');
    requireObject(lock.packages, 'Locked packages');
    const exception = validatePolicy(policy);
    if (blocking.length === 0) {
      console.log('No high/critical advisories; no exception used.');
      return 0;
    }
    validateException(blocking, lock, exception, contextDir);
    console.warn(`TEMPORARY SECURITY EXCEPTION: ${ADVISORY}; repository=${exception.repository}; owner=${exception.owner}; reason=${exception.reason}; expires=${exception.expiresAt}. The advisory remains unresolved; all other high/critical findings block.`);
    return 0;
  } catch (error) {
    console.error(`npm audit gate rejected: ${error.message}`);
    return 1;
  }
}

process.exitCode = main();
