/**
 * Flow tag constants for consistent E2E test tagging.
 *
 * Each constant bundles @flow:, @module:, and @priority: tags.
 * Use spread syntax to compose tags in tests:
 *
 *   import { AUTH_LOGIN_INVALID } from '../helpers/flow-tags';
 *   test('...', { tag: [...AUTH_LOGIN_INVALID] }, async ({ page }) => { ... });
 */

// ── Home ──
export const HOME_LOADS = ['@flow:home-loads', '@module:home', '@priority:P1'];
export const HOME_TO_BLOG = ['@flow:home-to-blog', '@module:home', '@priority:P2'];
export const HOME_TO_CATALOG = ['@flow:home-to-catalog', '@module:home', '@priority:P2'];
export const HOME_PRODUCT_CAROUSEL = ['@flow:home-product-carousel', '@module:home', '@priority:P3'];

// ── Auth ──
export const AUTH_SIGN_IN_FORM = ['@flow:auth-sign-in-form', '@module:auth', '@priority:P2'];
export const AUTH_SIGN_UP_FORM = ['@flow:auth-sign-up-form', '@module:auth', '@priority:P1'];
export const AUTH_LOGIN_INVALID = ['@flow:auth-login-invalid', '@module:auth', '@priority:P1'];
export const AUTH_PROTECTED_REDIRECT = ['@flow:auth-protected-redirect', '@module:auth', '@priority:P1'];
export const AUTH_FORGOT_PASSWORD_FORM = ['@flow:auth-forgot-password-form', '@module:auth', '@priority:P2'];
export const AUTH_BACKOFFICE_ACCESS = ['@flow:auth-backoffice-access', '@module:auth', '@priority:P1'];

// ── Blog ──
export const BLOG_LIST_VIEW = ['@flow:blog-list-view', '@module:blog', '@priority:P2'];
export const BLOG_DETAIL_VIEW = ['@flow:blog-detail-view', '@module:blog', '@priority:P2'];
export const BLOG_DETAIL_BACK = ['@flow:blog-detail-back', '@module:blog', '@priority:P3'];

// ── Navigation ──
export const NAVIGATION_BETWEEN_PAGES = ['@flow:navigation-between-pages', '@module:navigation', '@priority:P2'];
export const NAVIGATION_HEADER = ['@flow:navigation-header', '@module:navigation', '@priority:P3'];
export const NAVIGATION_FOOTER = ['@flow:navigation-footer', '@module:navigation', '@priority:P4'];
export const NAVIGATION_UNKNOWN_ROUTE = ['@flow:navigation-unknown-route', '@module:navigation', '@priority:P3'];

// ── Catalog ──
export const CATALOG_BROWSE = ['@flow:catalog-browse', '@module:catalog', '@priority:P1'];
export const CATALOG_PRODUCT_DETAIL = ['@flow:catalog-product-detail', '@module:catalog', '@priority:P1'];
export const CATALOG_PRODUCT_GALLERY = ['@flow:catalog-product-gallery', '@module:catalog', '@priority:P3'];
export const CATALOG_BACK_NAVIGATION = ['@flow:catalog-back-navigation', '@module:catalog', '@priority:P3'];

// ── Cart ──
export const CART_ADD = ['@flow:cart-add', '@module:cart', '@priority:P1'];
export const CART_EMPTY = ['@flow:cart-empty', '@module:cart', '@priority:P2'];
export const CART_UPDATE_QTY = ['@flow:cart-update-qty', '@module:cart', '@priority:P2'];
export const CART_REMOVE = ['@flow:cart-remove', '@module:cart', '@priority:P2'];
export const CART_SUBTOTAL = ['@flow:cart-subtotal', '@module:cart', '@priority:P2'];
export const CART_PERSIST = ['@flow:cart-persist', '@module:cart', '@priority:P2'];
export const CART_MULTIPLE_PRODUCTS = ['@flow:cart-multiple-products', '@module:cart', '@priority:P2'];
export const CART_QUANTITY_ZERO = ['@flow:cart-quantity-zero-removes-item', '@module:cart', '@priority:P2'];

// ── Checkout ──
export const CHECKOUT_FORM_DISPLAY = ['@flow:checkout-form-display', '@module:checkout', '@priority:P2'];
export const CHECKOUT_FORM_VALIDATION = ['@flow:checkout-form-validation', '@module:checkout', '@priority:P1'];
export const CHECKOUT_FORM_FILL = ['@flow:checkout-form-fill', '@module:checkout', '@priority:P2'];
export const CHECKOUT_SUBMIT_FAILURE = ['@flow:checkout-submit-failure', '@module:checkout', '@priority:P1'];

// ── Purchase ──
export const PURCHASE_COMPLETE_FLOW = ['@flow:purchase-complete-flow', '@module:purchase', '@priority:P1'];
export const PURCHASE_MULTIPLE_ITEMS = ['@flow:purchase-multiple-items', '@module:purchase', '@priority:P2'];
export const PURCHASE_DISABLED_EMPTY_CART = ['@flow:purchase-disabled-empty-cart', '@module:purchase', '@priority:P2'];
export const PURCHASE_LOADING_STATE = ['@flow:purchase-loading-state', '@module:purchase', '@priority:P3'];
