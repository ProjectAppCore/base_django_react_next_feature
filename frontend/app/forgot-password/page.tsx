'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { FormEvent, useState } from 'react';

import { useAuthStore } from '@/lib/stores/authStore';
import { getApiErrorMessage } from '@/lib/services/errors';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { sendPasswordResetCode, resetPassword } = useAuthStore();

  const [step, setStep] = useState<'email' | 'code'>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const onSendCode = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      await sendPasswordResetCode(email);
      setMessage('Verification code sent to your email');
      setStep('code');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to send code'));
    } finally {
      setLoading(false);
    }
  };

  const onResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    // Validate passwords match
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    // Validate password strength
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      setLoading(false);
      return;
    }

    try {
      await resetPassword({ email, code, new_password: newPassword });
      setMessage('Password reset successfully! Redirecting...');
      router.replace('/sign-in');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to reset password'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-md mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold">Reset Password</h1>

      {step === 'email' ? (
        <form className="mt-6 space-y-4" onSubmit={onSendCode}>
          <p className="text-sm text-muted-foreground">
            Enter your email address and we&apos;ll send you a verification code to reset your password.
          </p>

          <div>
            <input
              className="border border-border rounded px-3 py-2 w-full bg-card"
              placeholder="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          <button
            className="bg-primary text-primary-foreground rounded px-4 py-2 w-full disabled:opacity-50 hover:bg-primary/90"
            type="submit"
            disabled={loading}
          >
            {loading ? 'Sending...' : 'Send verification code'}
          </button>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          {message ? <p className="text-success text-sm">{message}</p> : null}
        </form>
      ) : (
        <form className="mt-6 space-y-4" onSubmit={onResetPassword}>
          <p className="text-sm text-muted-foreground">
            Paste the complete recovery code sent to <strong>{email}</strong> and your new password.
          </p>

          <div>
            <input
              className="border border-border rounded px-3 py-2 w-full text-center text-2xl tracking-widest bg-card"
              placeholder="Recovery code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={64}
              required
            />
            <p className="text-xs text-muted-foreground mt-1">Copy the complete recovery code from your email</p>
          </div>

          <div>
            <input
              className="border border-border rounded px-3 py-2 w-full bg-card"
              placeholder="New Password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              type="password"
              autoComplete="new-password"
              required
            />
            <p className="text-xs text-muted-foreground mt-1">Must be at least 8 characters</p>
          </div>

          <div>
            <input
              className="border border-border rounded px-3 py-2 w-full bg-card"
              placeholder="Confirm New Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              type="password"
              autoComplete="new-password"
              required
            />
          </div>

          <button
            className="bg-primary text-primary-foreground rounded px-4 py-2 w-full disabled:opacity-50 hover:bg-primary/90"
            type="submit"
            disabled={loading}
          >
            {loading ? 'Resetting...' : 'Reset password'}
          </button>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          {message ? <p className="text-success text-sm">{message}</p> : null}

          <button
            type="button"
            onClick={() => setStep('email')}
            className="text-sm text-info hover:underline w-full text-center"
          >
            Back to email
          </button>
        </form>
      )}

      <div className="mt-6 text-center text-sm">
        <Link href="/sign-in" className="text-info hover:underline">
          Back to sign in
        </Link>
      </div>
    </main>
  );
}
