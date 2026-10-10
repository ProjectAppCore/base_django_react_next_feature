import { test, expect } from '../test-with-coverage';
import { waitForPageLoad } from '../fixtures';
import { BLOG_LIST_VIEW, BLOG_DETAIL_VIEW, BLOG_DETAIL_BACK } from '../helpers/flow-tags';

test.describe('Blog Pages', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/blogs');
    await waitForPageLoad(page);
  });

  test('reaches the blogs list from the header and shows blog cards', { tag: [...BLOG_LIST_VIEW, '@outcome:display'] }, async ({ page }) => {
    await page.goto('/');
    await waitForPageLoad(page);

    await page.getByRole('banner').getByRole('link', { name: 'Blogs' }).click();
    await expect(page).toHaveURL(/.*blogs/);

    // quality: allow-fragile-selector (blog list links uniquely scoped by href pattern)
    const blogCards = page.locator('a[href^="/blogs/"]');
    await expect(blogCards.first()).toBeVisible({ timeout: 15000 });
    await expect(blogCards.first()).toHaveAttribute('href', /\/blogs\/\d+/);
  });

  test('shows the blogs error state when the blog list request fails', { tag: [...BLOG_LIST_VIEW, '@outcome:failure'] }, async ({ page }) => {
    // Catches a regression that leaves the blogs page stuck on its loading
    // skeleton (or crashes) instead of showing the error+retry affordance
    // when the blog list request fails.
    // quality: allow-no-interaction (the error state renders automatically from the failed background fetch on page mount; there is no prior user action that triggers it)
    await page.route('**/blogs/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );

    await page.goto('/blogs');
    await waitForPageLoad(page);

    await expect(page.getByText('Blogs unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });

  test('the blog detail shows the post title from the list', { tag: [...BLOG_DETAIL_VIEW, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-fragile-selector (blog list links uniquely scoped by href pattern)
    const firstCard = page.locator('a[href^="/blogs/"]').first();
    await expect(firstCard).toBeVisible({ timeout: 15000 });
    const title = ((await firstCard.locator('h3').first().textContent()) ?? '').trim();
    expect(title.length).toBeGreaterThan(0);

    await firstCard.click();
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/.*blogs\/\d+/);

    await expect(page.getByText(title, { exact: false }).first()).toBeVisible();
  });

  test('returns to the blog list from an invalid detail URL', { tag: [...BLOG_DETAIL_VIEW, '@outcome:error'] }, async ({ page }) => {
    await page.goto('/blogs/not-a-number');
    await expect(page.getByText('Blog not found.')).toBeVisible();

    await page.getByRole('link', { name: 'Back to blogs' }).click();

    await expect(page).toHaveURL(/\/blogs$/);
    await expect(page.getByRole('heading', { name: 'Blogs', exact: true })).toBeVisible();
  });

  test('returns to the blog list after a missing post', { tag: [...BLOG_DETAIL_VIEW, '@outcome:error'] }, async ({ page }) => {
    await page.route('**/blogs/999999/', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/blogs/999999');
    await expect(page.getByText('Blog not found.')).toBeVisible();

    await page.getByRole('link', { name: 'Back to blogs' }).click();

    await expect(page).toHaveURL(/\/blogs$/);
    await expect(page.getByRole('heading', { name: 'Blogs', exact: true })).toBeVisible();
  });

  test('keeps a failed post recoverable after a rejected retry', { tag: [...BLOG_DETAIL_VIEW, '@outcome:failure'] }, async ({ page }) => {
    await page.route('**/blogs/999999/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/blogs/999999');
    await expect(page.getByText('Blog unavailable')).toBeVisible();
    const retryResponse = page.waitForResponse((response) => response.url().endsWith('/blogs/999999/'));

    await page.getByRole('button', { name: 'Retry' }).click();
    expect((await retryResponse).status()).toBe(500);

    await expect(page.getByText('Blog unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to blogs' })).toBeVisible();
  });

  test('loads the post after an explicit retry succeeds', { tag: [...BLOG_DETAIL_VIEW, '@outcome:success'] }, async ({ page }) => {
    const recoveredBlog = {
      id: 999999,
      title: 'Recovered blog',
      category: 'Tips',
      description: 'Content restored',
      image_url: '',
    };
    await page.route('**/blogs/999999/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(recoveredBlog) })
    );
    await page.route('**/blogs/999999/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' }),
    { times: 1 });
    await page.goto('/blogs/999999');
    await expect(page.getByText('Blog unavailable')).toBeVisible();

    await page.getByRole('button', { name: 'Retry' }).click();

    await expect(page.getByRole('heading', { name: recoveredBlog.title })).toBeVisible();
    await expect(page.getByText(recoveredBlog.description)).toBeVisible();
  });

  test('should navigate back to blogs list from detail', { tag: [...BLOG_DETAIL_BACK, '@outcome:success'] }, async ({ page }) => {
    const blogCards = page.locator('a[href^="/blogs/"]');
    await expect(blogCards.first()).toBeVisible({ timeout: 15000 });

    // quality: allow-fragile-selector (blog list links uniquely scoped by href pattern)
    await blogCards.first().click();
    await expect(page).toHaveURL(/.*blogs\/\d+/);

    // Go back — client-side back navigation fires no 'load' event, so rely on
    // the URL assertion's own retry rather than waitForPageLoad.
    await page.goBack();

    // Verify we're back on blogs list
    await expect(page).toHaveURL(/.*blogs$/, { timeout: 15000 });
  });
});
