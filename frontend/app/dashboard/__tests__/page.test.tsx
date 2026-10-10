import { describe, it, expect, beforeEach } from '@jest/globals';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/navigation';

import DashboardPage from '../page';
import { useAuthStore } from '../../../lib/stores/authStore';
import { api } from '../../../lib/services/http';
import { getAccessToken, getRefreshToken, clearTokens } from '../../../lib/services/tokens';

jest.mock('next/navigation', () => ({ useRouter: jest.fn() }));
jest.mock('../../../lib/services/http', () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock('../../../lib/services/tokens', () => ({
  getAccessToken: jest.fn(), getRefreshToken: jest.fn(), clearTokens: jest.fn(), setTokens: jest.fn(),
}));

const replace = jest.fn();
const mockGetAccessToken = getAccessToken as jest.Mock;
const mockGetRefreshToken = getRefreshToken as jest.Mock;
const mockClearTokens = clearTokens as jest.Mock;
const user = { id: 1, email: 'user@example.com', first_name: 'Test', last_name: 'User', role: 'admin', is_staff: false };

describe('DashboardPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({ replace });
    mockGetAccessToken.mockReturnValue('access');
    mockGetRefreshToken.mockReturnValue('refresh');
    mockClearTokens.mockImplementation(() => {
      mockGetAccessToken.mockReturnValue(null);
      mockGetRefreshToken.mockReturnValue(null);
    });
    useAuthStore.setState({ user, accessToken: 'access', refreshToken: 'refresh', isAuthenticated: true });
  });

  it('redirects visitors to sign in', async () => {
    mockGetAccessToken.mockReturnValue(null);
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });

    const { container } = render(<DashboardPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/sign-in'));
    expect(container).toBeEmptyDOMElement();
  });

  it('hides backoffice from customers', () => {
    render(<DashboardPage />);

    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Backoffice' })).not.toBeInTheDocument();
  });

  it('shows backoffice to staff with a customer role label', () => {
    useAuthStore.setState({ user: { ...user, role: 'customer', is_staff: true } });

    render(<DashboardPage />);

    expect(screen.getByRole('link', { name: 'Backoffice' })).toHaveAttribute('href', '/backoffice');
  });

  it('hides backoffice while the user is unknown', () => {
    useAuthStore.setState({ user: null });
    (api.get as jest.Mock).mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);

    expect(screen.queryByRole('link', { name: 'Backoffice' })).not.toBeInTheDocument();
  });

  it('signs out through the existing session action', async () => {
    render(<DashboardPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(mockClearTokens).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/sign-in'));
  });
});
