import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ForgotPasswordPage from '../page';
import { useAuthStore } from '../../../lib/stores/authStore';
import { useRouter } from 'next/navigation';

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('../../../lib/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));

const mockUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockUseRouter = useRouter as unknown as jest.Mock;

const setAuthStoreState = (state: any) => {
  mockUseAuthStore.mockImplementation((selector?: (store: any) => unknown) =>
    selector ? selector(state) : state
  );
};

const submitEmail = () => {
  fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'user@example.com' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
};

const advanceToCodeStep = async () => {
  submitEmail();
  await screen.findByRole('textbox', { name: 'Recovery code', exact: true });
};

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('sends reset code and moves to code step', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    setAuthStoreState({ sendPasswordResetCode, resetPassword: jest.fn() });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    await waitFor(() => {
      expect(sendPasswordResetCode).toHaveBeenCalledWith('user@example.com');
    });

    expect(screen.getByRole('textbox', { name: 'Recovery code', exact: true })).toHaveAttribute('maxLength', '64');
    expect(screen.getByText('Verification code sent to your email')).toBeInTheDocument();
  });

  it('shows error when sending code fails', async () => {
    const sendPasswordResetCode = jest
      .fn()
      .mockRejectedValue({ response: { data: { error: 'Failed to send code' } } });
    setAuthStoreState({ sendPasswordResetCode, resetPassword: jest.fn() });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    submitEmail();

    expect(await screen.findByText('Failed to send code')).toBeInTheDocument();
  });

  it('shows default error when sending code fails without response', async () => {
    const sendPasswordResetCode = jest.fn().mockRejectedValue(new Error('boom'));
    setAuthStoreState({ sendPasswordResetCode, resetPassword: jest.fn() });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    submitEmail();

    expect(await screen.findByText('Failed to send code')).toBeInTheDocument();
  });

  it('validates password mismatch', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    const resetPassword = jest.fn();
    setAuthStoreState({ sendPasswordResetCode, resetPassword });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery code', exact: true }), { target: { value: 'd4x5z6-0123456789abcdef0123456789abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'password456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    // Bug this catches: a mismatch-validation regression that clears/loses the
    // already-verified recovery code, forcing the user to re-request one.
    expect(screen.getByRole('textbox', { name: 'Recovery code', exact: true })).toHaveValue('d4x5z6-0123456789abcdef0123456789abcdef');
  });

  it('validates password length', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    const resetPassword = jest.fn();
    setAuthStoreState({ sendPasswordResetCode, resetPassword });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery code', exact: true }), { target: { value: 'd4x5z6-0123456789abcdef0123456789abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'short' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    expect(await screen.findByText('Password must be at least 8 characters')).toBeInTheDocument();
    // Bug this catches: a length-validation regression that clears/loses the
    // already-verified recovery code, forcing the user to re-request one.
    expect(screen.getByRole('textbox', { name: 'Recovery code', exact: true })).toHaveValue('d4x5z6-0123456789abcdef0123456789abcdef');
  });

  it('resets password and redirects on success', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    const resetPassword = jest.fn().mockResolvedValue(undefined);
    const replace = jest.fn();

    setAuthStoreState({ sendPasswordResetCode, resetPassword });
    mockUseRouter.mockReturnValue({ replace });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery code', exact: true }), { target: { value: 'd4x5z6-0123456789abcdef0123456789abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    await waitFor(() => {
      expect(resetPassword).toHaveBeenCalledWith({
        email: 'user@example.com',
        code: 'd4x5z6-0123456789abcdef0123456789abcdef',
        new_password: 'password123',
      });
    });

    expect(screen.getByText('Password reset successfully! Redirecting...')).toBeInTheDocument();

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith('/sign-in');
    }, { timeout: 3000 });
  });

  it('shows error when reset fails', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    const resetPassword = jest
      .fn()
      .mockRejectedValue({ response: { data: { error: 'Failed to reset password' } } });
    setAuthStoreState({ sendPasswordResetCode, resetPassword });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery code', exact: true }), { target: { value: 'd4x5z6-0123456789abcdef0123456789abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    expect(await screen.findByText('Failed to reset password')).toBeInTheDocument();
  });

  it('shows default error when reset fails without response', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    const resetPassword = jest.fn().mockRejectedValue(new Error('boom'));
    setAuthStoreState({ sendPasswordResetCode, resetPassword });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.change(screen.getByRole('textbox', { name: 'Recovery code', exact: true }), { target: { value: 'd4x5z6-0123456789abcdef0123456789abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('New Password'), { target: { value: 'password123' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm New Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    expect(await screen.findByText('Failed to reset password')).toBeInTheDocument();
  });

  it('allows returning to email step', async () => {
    const sendPasswordResetCode = jest.fn().mockResolvedValue(undefined);
    setAuthStoreState({ sendPasswordResetCode, resetPassword: jest.fn() });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    render(<ForgotPasswordPage />);

    await advanceToCodeStep();

    fireEvent.click(screen.getByRole('button', { name: 'Back to email' }));

    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
  });
});
