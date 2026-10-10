import { test, expect } from '../test-with-coverage';
import { waitForPageLoad } from '../fixtures';
import { CATALOG_PRODUCT_DETAIL, CATALOG_PRODUCT_GALLERY, CATALOG_BACK_NAVIGATION } from '../helpers/flow-tags';

test.describe('Product Pages', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/catalog');
    await waitForPageLoad(page);
  });

  test('opens a product from the catalog', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });
    await productCards.first().click();
    await waitForPageLoad(page);

    await expect(page).toHaveURL(/.*products\/\d+/);
  });

  test('the product detail shows the listed title and its price', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const firstCard = page.locator('a[href^="/products/"]').first();
    await expect(firstCard).toBeVisible({ timeout: 15000 });
    const title = ((await firstCard.locator('h3').first().textContent()) ?? '').trim();
    expect(title.length).toBeGreaterThan(0);

    await firstCard.click();
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/.*products\/\d+/);

    await expect(page.getByText(title, { exact: false }).first()).toBeVisible();
    // Price is rendered as $<digits> on the detail page.
    await expect(page.getByText(/\$\d/).first()).toBeVisible();
  });

  test('shows a recoverable state when the product detail request fails', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:failure'] }, async ({ page }) => {
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });

    // Glob is scoped to a detail id (`*`) so the catalog's own list request,
    // used above to render the cards, is never intercepted.
    await page.route('**/products/*/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );
    await productCards.first().click();

    await expect(page.getByText('Product unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to catalog' })).toBeVisible();
  });

  test('returns to the catalog after a missing product', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:error'] }, async ({ page }) => {
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/products/999999');
    await expect(page.getByText('Product not found.')).toBeVisible();

    await page.getByRole('link', { name: 'Back to catalog' }).click();

    await expect(page).toHaveURL(/\/catalog$/);
    await expect(page.getByRole('heading', { name: 'Catalog', exact: true })).toBeVisible();
  });

  test('loads the product after an explicit retry succeeds', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:success'] }, async ({ page }) => {
    const recoveredProduct = {
      id: 999999, title: 'Recovered product', category: 'Candles',
      description: 'Product restored', price: 45, gallery_urls: [],
    };
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/products/999999');
    await expect(page.getByText('Product unavailable')).toBeVisible();
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(recoveredProduct) })
    );

    await page.getByRole('button', { name: 'Retry' }).click();

    await expect(page.getByRole('heading', { name: recoveredProduct.title })).toBeVisible();
    await expect(page.getByText('$45', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add to cart' })).toBeVisible();
  });

  test('keeps a failed product recoverable after another rejected retry', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:failure'] }, async ({ page }) => {
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/products/999999');
    await expect(page.getByText('Product unavailable')).toBeVisible();
    const retryResponse = page.waitForResponse((response) => response.url().endsWith('/products/999999/'));

    await page.getByRole('button', { name: 'Retry' }).click();
    expect((await retryResponse).status()).toBe(500);

    await expect(page.getByText('Product unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to catalog' })).toBeVisible();
  });

  test('shows a missing product when retry returns 404', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:error'] }, async ({ page }) => {
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );
    await page.goto('/products/999999');
    await expect(page.getByText('Product unavailable')).toBeVisible();
    await page.route('**/products/999999/', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
    );

    await page.getByRole('button', { name: 'Retry' }).click();

    await expect(page.getByText('Product not found.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to catalog' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toHaveCount(0);
  });

  test('keeps a network failure recoverable', { tag: [...CATALOG_PRODUCT_DETAIL, '@outcome:failure'] }, async ({ page }) => {
    await page.route('**/products/999999/', (route) => route.abort('failed'));

    await page.goto('/products/999999');

    await expect(page.getByText('Product unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to catalog' })).toBeVisible();
  });

  test('the product detail renders a gallery image with a source', { tag: [...CATALOG_PRODUCT_GALLERY, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    const firstCard = productCards.first();
    await expect(firstCard).toBeVisible({ timeout: 15000 });
    const title = ((await firstCard.locator('h3').first().textContent()) ?? '').trim();

    await firstCard.click();
    await waitForPageLoad(page);

    // Scoped by the product's own title (the gallery image's alt text) so
    // this cannot pass on an unrelated placeholder image.
    const galleryImage = page.getByRole('img', { name: title }).first();
    await expect(galleryImage).toBeVisible();
    await expect(galleryImage).toHaveAttribute('src', /.+/);
  });

  test('navigates back to the catalog from a product', { tag: [...CATALOG_BACK_NAVIGATION, '@outcome:success'] }, async ({ page }) => {
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });
    await productCards.first().click();
    await expect(page).toHaveURL(/.*products\/\d+/);

    // Client-side back navigation fires no 'load' event, so rely on the URL
    // assertion's retry rather than waitForPageLoad.
    await page.goBack();
    await expect(page).toHaveURL(/.*catalog/, { timeout: 15000 });
  });
});
