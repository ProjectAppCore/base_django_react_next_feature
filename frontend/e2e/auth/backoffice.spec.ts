import { execFile } from 'node:child_process';
import { lstat, realpath } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { promisify } from 'node:util';
import type { Page, FullConfig, TestConfig } from '@playwright/test';

import { test, expect } from '../test-with-coverage';
import { testUser, testAdminUser } from '../fixtures';
import { AUTH_BACKOFFICE_ACCESS } from '../helpers/flow-tags';

const runFile = promisify(execFile);
const projectRoot = path.resolve(__dirname, '../../..');
const backendRoot = path.join(projectRoot, 'backend');
const databasePath = path.join(backendRoot, 'db.sqlite3');
const settingsModule = 'base_feature_project.settings_dev';
const databaseEngine = 'django.db.backends.sqlite3';

function requireLoopback(value: string): URL {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol)
      || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
      || url.username || url.password) {
    throw new Error('Backoffice E2E requires loopback frontend and API origins.');
  }
  return url;
}

async function prepareAccounts(config: FullConfig) {
  if (process.env.PYTHON_DOTENV_DISABLED !== '1'
      || process.env.DJANGO_SETTINGS_MODULE !== settingsModule
      || process.env.DJANGO_DB_ENGINE !== databaseEngine
      || process.env.DJANGO_DB_NAME !== databasePath) {
    throw new Error('Backoffice E2E requires settings_dev with dotenv disabled and this worktree SQLite database.');
  }
  if (!config.configFile) {
    throw new Error('Backoffice E2E requires the original Playwright configuration file.');
  }
  // FullConfig.webServer is null for multiple servers; read the selected source config.
  const configModule = createRequire(__filename)(config.configFile) as TestConfig & { default?: TestConfig };
  const webServer = (configModule.default ?? configModule).webServer;
  const servers = Array.isArray(webServer) ? webServer : [webServer];
  if (servers.length !== 2 || servers.some((server) => !server || server.reuseExistingServer !== false)) {
    throw new Error('Backoffice E2E requires two new servers; existing servers cannot be reused.');
  }
  const serverOrigins = servers.map((server) => requireLoopback(server!.url!).origin);
  const frontend = requireLoopback(String(config.projects[0].use.baseURL));
  const backend = requireLoopback(process.env.NEXT_PUBLIC_BACKEND_ORIGIN || 'http://localhost:8000');
  if (!serverOrigins.includes(frontend.origin)
      || !servers.some((server) => requireLoopback(server!.url!).port === backend.port)) {
    throw new Error('Backoffice E2E frontend and proxy backend must match the newly started servers.');
  }
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '/api';
  const apiUrl = requireLoopback(new URL(apiBase, frontend).href);
  if (!serverOrigins.includes(apiUrl.origin) || apiUrl.pathname.replace(/\/$/, '') !== '/api') {
    throw new Error('Backoffice E2E API must use the isolated loopback servers.');
  }
  const database = await lstat(databasePath);
  if (!database.isFile() || database.isSymbolicLink() || await realpath(databasePath) !== databasePath) {
    throw new Error('Backoffice E2E database must be a regular file inside this worktree.');
  }
  const accounts = [
    { ...testUser, is_staff: false, role: 'customer' },
    { ...testAdminUser, is_staff: true, role: 'admin' },
  ];
  const script = `
import json
import os
import sqlite3
import sys
from pathlib import Path

expected_database = Path(sys.argv[1])
assert os.environ['PYTHON_DOTENV_DISABLED'] == '1'
assert os.environ['DJANGO_SETTINGS_MODULE'] == '${settingsModule}'
assert os.environ['DJANGO_DB_ENGINE'] == '${databaseEngine}'
assert os.environ['DJANGO_DB_NAME'] == str(expected_database)
assert expected_database.is_file() and not expected_database.is_symlink()
assert expected_database.resolve(strict=True) == expected_database
with sqlite3.connect(expected_database.as_uri() + '?mode=ro', uri=True) as db:
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='base_feature_app_user'").fetchone(), 'Create the isolated schema before running E2E.'
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
assert settings.DATABASES['default']['ENGINE'] == '${databaseEngine}'
assert Path(settings.DATABASES['default']['NAME']).resolve(strict=True) == expected_database
assert settings.BASE_DIR.resolve() == expected_database.parent
with transaction.atomic():
    for account in json.loads(sys.argv[2]):
        user, _ = get_user_model().objects.get_or_create(email=account['email'])
        user.set_password(account['password'])
        user.is_active = True
        user.is_staff = account['is_staff']
        user.is_superuser = False
        user.role = account['role']
        user.save(update_fields=['password', 'is_active', 'is_staff', 'is_superuser', 'role'])
`;
  await runFile(path.join(backendRoot, 'venv/bin/python'), ['-c', script, databasePath, JSON.stringify(accounts)], {
    cwd: backendRoot,
    env: { ...process.env, PYTHON_DOTENV_DISABLED: '1', DJANGO_SETTINGS_MODULE: settingsModule },
  });
}

async function login(page: Page, account: typeof testUser, isStaff: boolean) {
  await page.goto('/sign-in');
  await page.getByPlaceholder('Email').fill(account.email);
  await page.getByPlaceholder('Password', { exact: true }).fill(account.password);
  const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/sign_in/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const session = await response.json();
  expect(session.user.email).toBe(account.email);
  expect(session.user.is_staff).toBe(isStaff);
  const validation = await page.request.get('/api/validate_token/', {
    headers: { Authorization: `Bearer ${session.access}` },
  });
  expect(validation.status()).toBe(200);
  expect((await validation.json()).user.is_staff).toBe(isStaff);
  await expect(page).toHaveURL(/\/dashboard$/);
}

function administrativeRequests(page: Page) {
  const requests: string[] = [];
  page.on('request', (request) => {
    if (/\/api\/(users|sales)\/$/.test(new URL(request.url()).pathname)) {
      requests.push(request.url());
    }
  });
  return requests;
}

test.describe('Administrative backoffice access', () => {
  test.beforeAll(async ({ request }, testInfo) => {
    await prepareAccounts(testInfo.config);
    const health = await request.get('/api/health/');
    expect(health.status()).toBe(200);
    expect((await health.json()).project).toBe(path.basename(projectRoot));
  });

  test('hides the backoffice link from a customer', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:display'] }, async ({ page }) => {
    await login(page, testUser, false);

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Backoffice', exact: true })).toHaveCount(0);
  });

  test('denies direct customer access', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:error'] }, async ({ page }) => {
    await login(page, testUser, false);
    const protectedRequests = administrativeRequests(page);

    // quality: allow-no-interaction (a customer has no Backoffice link; direct URL access is the permission boundary)
    await page.goto('/backoffice');

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible();
    await expect(page.getByRole('alert')).toHaveText('Admin access required.');
    await expect(page.getByRole('table')).toHaveCount(0);
    expect(protectedRequests).toHaveLength(0);
    await page.getByRole('link', { name: 'Back to dashboard' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('shows administrative lists after staff navigation', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:success'] }, async ({ page }) => {
    await login(page, testAdminUser, true);

    await page.getByRole('link', { name: 'Backoffice', exact: true }).click();

    await expect(page.getByRole('heading', { name: 'Backoffice' })).toBeVisible();
    await expect(page.getByRole('table')).toHaveCount(2);
    await expect(page.getByRole('table').first().getByText(testUser.email, { exact: true })).toBeVisible();
    await expect(page.getByRole('table').nth(1).locator('tbody tr').first()).not.toHaveText('No data');
  });

  test('restores staff access after a reload', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:display'] }, async ({ page }) => {
    await login(page, testAdminUser, true);
    await page.getByRole('link', { name: 'Backoffice', exact: true }).click();
    await expect(page.getByRole('table')).toHaveCount(2);

    await page.reload();

    await expect(page.getByRole('table')).toHaveCount(2);
    await expect(page.getByRole('table').first().getByText(testUser.email, { exact: true })).toBeVisible();
  });

  test('waits for validation before requesting administrative lists', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:display'] }, async ({ page }) => {
    await login(page, testAdminUser, true);
    let release!: () => void;
    const validationGate = new Promise<void>((resolve) => { release = resolve; });
    await page.route('**/validate_token/', async (route) => {
      await validationGate;
      await route.continue();
    });
    const protectedRequests = administrativeRequests(page);

    await page.getByRole('link', { name: 'Backoffice', exact: true }).click();

    try {
      await expect(page.getByText('Checking access...')).toBeVisible();
      await expect(page.getByRole('table')).toHaveCount(0);
      expect(protectedRequests).toHaveLength(0);
    } finally {
      release();
    }
    await expect(page.getByRole('table')).toHaveCount(2);
  });

  test('shows denial when the API rejects administrative access', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:error'] }, async ({ page }) => {
    await login(page, testAdminUser, true);
    await page.route('**/users/', (route) => route.fulfill({
      status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Admin access required.' }),
    }));

    await page.getByRole('link', { name: 'Backoffice', exact: true }).click();

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible();
    await expect(page.getByRole('table')).toHaveCount(0);
  });

  test('shows a temporary loading failure after an HTTP error', { tag: [...AUTH_BACKOFFICE_ACCESS, '@outcome:failure'] }, async ({ page }) => {
    await login(page, testAdminUser, true);
    await page.route('**/users/', (route) => route.fulfill({ status: 500, body: '{}' }));

    await page.getByRole('link', { name: 'Backoffice', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not load backoffice data.');
    await expect(page.getByRole('table')).toHaveCount(0);
    await expect(page.getByText('No data')).toHaveCount(0);
  });
});
