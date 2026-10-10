import { test, expect } from '../test-with-coverage';
import { waitForPageLoad, testCheckoutData } from '../fixtures';
import { PURCHASE_COMPLETE_FLOW, PURCHASE_MULTIPLE_ITEMS, PURCHASE_DISABLED_EMPTY_CART, PURCHASE_LOADING_STATE, HOME_PRODUCT_CAROUSEL } from '../helpers/flow-tags';

test.describe('Complete Purchase Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear cart before each test
    await page.goto('/checkout');
    await page.evaluate(() => localStorage.clear());
  });

  // quality: disable too_many_assertions (multi-step purchase flow requires asserting each navigation step)
  // quality: disable test_too_long (this is the only test in the suite that drives the full home-to-completed-sale journey and cannot be split without losing flow context)
  test('should complete full purchase flow from home to checkout', { tag: [...PURCHASE_COMPLETE_FLOW, '@outcome:success'] }, async ({ page }) => {
    // Catches a regression anywhere along the full purchase journey — the
    // "Shop now" CTA, add-to-cart, the checkout form, or the submit handler —
    // that stops a real purchase from actually completing.
    // 1. Start at home page
    await page.goto('/');
    await waitForPageLoad(page);
    await expect(page.getByRole('heading', { name: 'Everything you need, in one place' })).toBeVisible();

    // 2. Click "Shop now" to reach the catalog
    await page.getByRole('link', { name: 'Shop now' }).click();
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/.*catalog/);

    // 3. Click on first product
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });
    const firstProduct = productCards.first();
    const productTitle = ((await firstProduct.locator('h3').first().textContent()) ?? '').trim();

    await firstProduct.click();
    await waitForPageLoad(page);

    // 4. Verify we're on product detail page
    await expect(page).toHaveURL(/.*products\/\d+/);
    await expect(page.getByRole('heading', { name: productTitle })).toBeVisible();

    // 5. Add product to cart
    const addToCartBtn = page.getByRole('button', { name: 'Add to cart' });
    await expect(addToCartBtn).toBeVisible();
    await addToCartBtn.click();

    // 6. Navigate to checkout
    await page.goto('/checkout');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/.*checkout/);

    // 7. Verify product is in cart
    await expect(page.getByText('Your cart is empty')).toBeHidden();
    await expect(page.getByText(productTitle)).toBeVisible();

    // 8. Fill checkout form
    await page.getByPlaceholder('Email').fill(testCheckoutData.email);
    await page.getByPlaceholder('Address').fill(testCheckoutData.address);
    await page.getByPlaceholder('City').fill(testCheckoutData.city);
    await page.getByPlaceholder('State').fill(testCheckoutData.state);
    await page.getByPlaceholder('Postal code').fill(testCheckoutData.postal_code);

    const submitBtn = page.getByRole('button', { name: 'Complete checkout' });
    await expect(submitBtn).toBeEnabled();

    // 9. Submit to the real API and verify the sale persisted by checkout.
    const saleResponsePromise = page.waitForResponse((response) =>
      response.url().endsWith('/create-sale/') && response.request().method() === 'POST'
    );
    await submitBtn.click();
    const saleResponse = await saleResponsePromise;
    expect(saleResponse.status()).toBe(201);
    const sale = await saleResponse.json();
    expect(sale.id).toEqual(expect.any(Number));
    expect(sale.email).toBe(testCheckoutData.email);
    expect(sale.sold_products).toHaveLength(1);
    expect(sale.sold_products[0].product.title).toBe(productTitle);
    expect(sale.sold_products[0].quantity).toBe(1);

    // 10. The purchase is only "complete" if the success state is visible and
    // the cart the user just bought from is actually cleared.
    await expect(page.getByText('Checkout completed.')).toBeVisible();
    await expect(page.getByText('Your cart is empty.')).toBeVisible();
  });

  test('should navigate through product carousel', { tag: [...HOME_PRODUCT_CAROUSEL, '@outcome:display'] }, async ({ page }) => {
    // Catches a regression where the home page's product carousel stops
    // linking to the right product (or to a product detail page at all).
    await page.goto('/');
    await waitForPageLoad(page);

    // Look for products in carousel
    // quality: allow-fragile-selector (carousel products uniquely scoped by href pattern)
    const carouselProducts = page.locator('a[href^="/products/"]');
    await expect(carouselProducts.first()).toBeVisible({ timeout: 15000 });
    const title = ((await carouselProducts.first().locator('h3').first().textContent()) ?? '').trim();

    // Click product from home page carousel
    await carouselProducts.first().click();
    await waitForPageLoad(page);

    // Should be on product detail, showing the same product that was clicked
    await expect(page).toHaveURL(/.*products\/\d+/);
    await expect(page.getByRole('heading', { name: title })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add to cart' })).toBeVisible();
  });

  test('shows the carousel error state when the product list request fails', { tag: [...HOME_PRODUCT_CAROUSEL, '@outcome:failure'] }, async ({ page }) => {
    // Catches the same class of regression as the catalog page's error state,
    // but for the home page's ProductCarousel — a different render path off
    // the same store/endpoint that must be verified independently.
    // quality: allow-no-interaction (the error state renders automatically from the failed background fetch on page mount; there is no prior user action that triggers it)
    await page.route('**/products/', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
    );

    await page.goto('/');
    await waitForPageLoad(page);

    await expect(page.getByText('Products unavailable')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });

  test('checkout lists two products and their subtotal', { tag: [...PURCHASE_MULTIPLE_ITEMS, '@outcome:success'] }, async ({ page }) => {
    await page.goto('/catalog');
    await waitForPageLoad(page);

    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.nth(1)).toBeVisible({ timeout: 15000 });

    await productCards.nth(0).click();
    await waitForPageLoad(page);
    await page.locator('button:has-text("Add to cart")').click();

    await page.goto('/catalog');
    await waitForPageLoad(page);
    await page.locator('a[href^="/products/"]').nth(1).click();
    await waitForPageLoad(page);
    await page.locator('button:has-text("Add to cart")').click();

    await page.goto('/checkout');
    await waitForPageLoad(page);

    // Each cart item row renders its own Remove button, so two items => two buttons.
    await expect(page.getByRole('button', { name: 'Remove' })).toHaveCount(2);
    await expect(page.getByText('Subtotal')).toBeVisible();
  });

  test('the complete-checkout button is disabled when the cart is empty', { tag: [...PURCHASE_DISABLED_EMPTY_CART, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-no-interaction (the cart is empty by default after the beforeEach clear; this asserts the disabled state of that default)
    await page.goto('/checkout');
    await waitForPageLoad(page);

    await expect(page.getByText('Your cart is empty.')).toBeVisible();
    await expect(page.locator('button:has-text("Complete checkout")')).toBeDisabled();
  });

  test('should show loading state during form submission', { tag: [...PURCHASE_LOADING_STATE, '@outcome:success'] }, async ({ page }) => {
    // Add a product first
    await page.goto('/catalog');
    await waitForPageLoad(page);

    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    const productCards = page.locator('a[href^="/products/"]');
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });
    await productCards.first().click();
    await waitForPageLoad(page);
    await page.locator('button:has-text("Add to cart")').click();

    await page.goto('/checkout');
    await waitForPageLoad(page);

    // Fill form
    await page.locator('input[placeholder="Email"]').fill(testCheckoutData.email);
    await page.locator('input[placeholder="Address"]').fill(testCheckoutData.address);
    await page.locator('input[placeholder="City"]').fill(testCheckoutData.city);
    await page.locator('input[placeholder="State"]').fill(testCheckoutData.state);
    await page.locator('input[placeholder="Postal code"]').fill(testCheckoutData.postal_code);

    const submitBtn = page.locator('button[type="submit"]');

    // Hold the sale request in flight so the transient loading state is
    // observable instead of racing the response — that race is why the
    // assertion below was originally commented out.
    await page.route('**/create-sale/', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' });
    });

    await submitBtn.click();

    // While the request is in flight the button shows the loading label and
    // stays disabled. Catches a regression where submit never enters the
    // loading state and stays clickable, letting the user double-submit and
    // create a duplicate sale.
    await expect(submitBtn).toHaveText('...');
    await expect(submitBtn).toBeDisabled();
  });

  test('re-enables the submit button after the sale request fails', { tag: [...PURCHASE_LOADING_STATE, '@outcome:failure'] }, async ({ page }) => {
    // Catches a failed sale request that leaves the submit button permanently
    // stuck on "..."/disabled, locking the user out of retrying.
    await page.goto('/catalog');
    await waitForPageLoad(page);

    const productCards = page.locator('a[href^="/products/"]');
    // quality: allow-fragile-selector (product list links uniquely scoped by href pattern)
    await expect(productCards.first()).toBeVisible({ timeout: 15000 });
    await productCards.first().click();
    await waitForPageLoad(page);
    await page.locator('button:has-text("Add to cart")').click();

    await page.goto('/checkout');
    await waitForPageLoad(page);

    await page.locator('input[placeholder="Email"]').fill(testCheckoutData.email);
    await page.locator('input[placeholder="Address"]').fill(testCheckoutData.address);
    await page.locator('input[placeholder="City"]').fill(testCheckoutData.city);
    await page.locator('input[placeholder="State"]').fill(testCheckoutData.state);
    await page.locator('input[placeholder="Postal code"]').fill(testCheckoutData.postal_code);

    const submitBtn = page.locator('button[type="submit"]');

    // Same in-flight technique as the success test above, but resolving with
    // a server error — this is the transition the bug lives in.
    await page.route('**/create-sale/', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    });

    await submitBtn.click();
    await expect(submitBtn).toHaveText('...');

    await expect(page.getByText('Could not complete checkout.')).toBeVisible();
    await expect(submitBtn).toHaveText('Complete checkout');
    await expect(submitBtn).toBeEnabled();
  });
});
