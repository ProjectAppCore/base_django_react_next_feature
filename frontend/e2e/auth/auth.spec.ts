import { test, expect } from '../test-with-coverage';
import { waitForPageLoad } from '../fixtures';
import { AUTH_SIGN_IN_FORM, AUTH_SIGN_UP_FORM, AUTH_LOGIN_INVALID, AUTH_PROTECTED_REDIRECT, AUTH_FORGOT_PASSWORD_FORM } from '../helpers/flow-tags';

test.describe('Authentication', () => {

  test('should show validation on empty form submission', { tag: [...AUTH_SIGN_IN_FORM, '@outcome:error'] }, async ({ page }) => {
    await page.goto('/sign-in');
    await waitForPageLoad(page);
    
    // Try to submit empty form
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();
    
    // Should still be on sign-in page
    await expect(page).toHaveURL(/.*sign-in/);
  });

  test('should accept input in form fields', { tag: [...AUTH_SIGN_IN_FORM, '@outcome:display'] }, async ({ page }) => {
    await page.goto('/sign-in');
    await waitForPageLoad(page);
    
    // Fill email (using placeholder)
    const emailInput = page.getByPlaceholder('Email');
    await emailInput.fill('test@example.com');
    await expect(emailInput).toHaveValue('test@example.com');
    
    // Fill password
    const passwordInput = page.locator('input[type="password"]');
    await passwordInput.fill('password123');
    await expect(passwordInput).toHaveValue('password123');
  });

  test('should handle invalid credentials gracefully', { tag: [...AUTH_LOGIN_INVALID, '@outcome:error'] }, async ({ page }) => {
    // Catches a regression where the sign-in form stops surfacing the
    // backend's rejection message (frontend/app/sign-in/page.tsx:55) and
    // instead fails silently or shows nothing.
    await page.route('**/sign_in/', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: '{}' })
    );

    await page.goto('/sign-in');
    await waitForPageLoad(page);

    // Fill with invalid credentials (using placeholder)
    const emailInput = page.getByPlaceholder('Email');
    await emailInput.fill('invalid@example.com');

    const passwordInput = page.getByPlaceholder('Password');
    await passwordInput.fill('wrongpassword');

    // Submit
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    // Shows the backend's rejection message and stays on sign-in page
    await expect(page.getByText('Invalid credentials')).toBeVisible();
    await expect(page).toHaveURL(/.*sign-in/);
  });

  test('redirects to sign-in when opening the dashboard without a session', { tag: [...AUTH_PROTECTED_REDIRECT, '@outcome:success'] }, async ({ page }) => {
    // quality: allow-no-interaction (no UI link to /dashboard when logged out; the guard redirect on direct navigation is the behavior)
    await page.context().clearCookies();
    await page.addInitScript(() => localStorage.clear());
    await page.goto('/dashboard');
    await waitForPageLoad(page);

    await expect(page).toHaveURL(/.*sign-in/);
  });

  test('redirects to sign-in when opening the backoffice without a session', { tag: [...AUTH_PROTECTED_REDIRECT, '@outcome:success'] }, async ({ page }) => {
    // quality: allow-no-interaction (no UI link to /backoffice when logged out; the guard redirect on direct navigation is the behavior)
    await page.context().clearCookies();
    await page.addInitScript(() => localStorage.clear());
    await page.goto('/backoffice');
    await waitForPageLoad(page);

    await expect(page).toHaveURL(/.*sign-in/);
  });

  test('should validate password mismatch on sign-up', { tag: [...AUTH_SIGN_UP_FORM, '@outcome:error'] }, async ({ page }) => {
    await page.goto('/sign-up');
    await waitForPageLoad(page);

    // Fill form with mismatched passwords
    await page.getByPlaceholder('First Name').fill('Test');
    await page.getByPlaceholder('Last Name').fill('User');
    await page.getByPlaceholder('Email').fill('test@example.com');
    await page.getByPlaceholder('Password', { exact: true }).fill('password123');
    await page.getByPlaceholder('Confirm Password').fill('different456');

    await page.getByRole('button', { name: 'Create account' }).click();

    // Should show password mismatch error and stay on sign-up page
    await expect(page.getByText('Passwords do not match')).toBeVisible();
    await expect(page).toHaveURL(/.*sign-up/);
  });

  test('should accept input in sign-up form fields', { tag: [...AUTH_SIGN_UP_FORM, '@outcome:display'] }, async ({ page }) => {
    // Catches a broken/removed onChange handler on any sign-up field
    // (controlled-input wiring regression).
    await page.goto('/sign-up');
    await waitForPageLoad(page);

    const firstNameInput = page.getByPlaceholder('First Name');
    await firstNameInput.fill('Ana');
    await expect(firstNameInput).toHaveValue('Ana');

    const lastNameInput = page.getByPlaceholder('Last Name');
    await lastNameInput.fill('Garcia');
    await expect(lastNameInput).toHaveValue('Garcia');

    const emailInput = page.getByPlaceholder('Email');
    await emailInput.fill('ana@example.com');
    await expect(emailInput).toHaveValue('ana@example.com');

    const passwordInput = page.getByPlaceholder('Password', { exact: true });
    await passwordInput.fill('password123');
    await expect(passwordInput).toHaveValue('password123');

    const confirmPasswordInput = page.getByPlaceholder('Confirm Password');
    await confirmPasswordInput.fill('password123');
    await expect(confirmPasswordInput).toHaveValue('password123');
  });

  test('should navigate from sign-in to forgot password', { tag: [...AUTH_FORGOT_PASSWORD_FORM, '@outcome:display'] }, async ({ page }) => {
    await page.goto('/sign-in');
    await waitForPageLoad(page);

    // Click forgot password link
    const forgotLink = page.getByRole('link', { name: 'Forgot password?' });
    await expect(forgotLink).toBeVisible();
    await forgotLink.click();
    await page.waitForURL(/.*forgot-password/, { timeout: 10_000 });

    await expect(page).toHaveURL(/.*forgot-password/);
    await expect(page.getByRole('heading', { name: 'Reset Password' })).toBeVisible();
  });

  test('submits the complete recovery token', { tag: [...AUTH_FORGOT_PASSWORD_FORM, '@outcome:success'] }, async ({ page }) => {
    const token = 'd4x5z6-0123456789abcdef0123456789abcdef';
    await page.route('**/send_passcode/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Code sent successfully' }) })
    );
    await page.route('**/verify_passcode_and_reset_password/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Password reset successfully' }) })
    );
    await page.goto('/forgot-password');
    await page.getByPlaceholder('Email').fill('recovery@example.invalid');
    await page.getByRole('button', { name: 'Send verification code' }).click();
    await page.getByPlaceholder('Recovery code').fill(token);
    await expect(page.getByPlaceholder('Recovery code')).toHaveValue(token);
    await page.getByPlaceholder('New Password', { exact: true }).fill('new-password');
    await page.getByPlaceholder('Confirm New Password').fill('new-password');
    const submission = page.waitForRequest('**/verify_passcode_and_reset_password/');

    await page.getByRole('button', { name: 'Reset password', exact: true }).click();

    expect((await submission).postDataJSON()).toEqual({
      email: 'recovery@example.invalid', code: token, new_password: 'new-password',
    });
    await expect(page).toHaveURL(/.*sign-in/);
  });

  test('preserves the recovery token after rejection', { tag: [...AUTH_FORGOT_PASSWORD_FORM, '@outcome:error'] }, async ({ page }) => {
    const token = 'd4x5z6-0123456789abcdef0123456789abcdef';
    await page.route('**/send_passcode/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Code sent successfully' }) })
    );
    await page.route('**/verify_passcode_and_reset_password/', (route) =>
      route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ error: 'Invalid or expired code' }) })
    );
    await page.goto('/forgot-password');
    await page.getByPlaceholder('Email').fill('recovery@example.invalid');
    await page.getByRole('button', { name: 'Send verification code' }).click();
    await page.getByPlaceholder('Recovery code').fill(token);
    await page.getByPlaceholder('New Password', { exact: true }).fill('new-password');
    await page.getByPlaceholder('Confirm New Password').fill('new-password');

    await page.getByRole('button', { name: 'Reset password', exact: true }).click();

    await expect(page.getByText('Invalid or expired code')).toBeVisible();
    await expect(page.getByPlaceholder('Recovery code')).toHaveValue(token);
    await expect(page).toHaveURL(/.*forgot-password/);
  });


  test('allows retrying a failed recovery email', { tag: [...AUTH_FORGOT_PASSWORD_FORM, '@outcome:failure'] }, async ({ page }) => {
    const responses = [
      { status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Failed to send email' }) },
      { status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'Code sent successfully' }) },
    ];
    await page.route('**/send_passcode/', (route) => route.fulfill(responses.shift()!));
    await page.goto('/forgot-password');
    await page.getByPlaceholder('Email').fill('recovery@example.invalid');

    await page.getByRole('button', { name: 'Send verification code' }).click();

    await expect(page.getByText('Failed to send email')).toBeVisible();
    await expect(page.getByPlaceholder('Email')).toHaveValue('recovery@example.invalid');
    await expect(page.getByRole('button', { name: 'Send verification code' })).toBeEnabled();
    await page.getByRole('button', { name: 'Send verification code' }).click();
    await expect(page.getByPlaceholder('Recovery code')).toBeVisible();
  });

});
