import { describe, it, expect, beforeEach } from '@jest/globals';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { useRouter } from 'next/navigation';

import BackofficePage from '../page';
import { api } from '../../../lib/services/http';
import { useAuthStore } from '../../../lib/stores/authStore';
import { getAccessToken, getRefreshToken, clearTokens } from '../../../lib/services/tokens';

jest.mock('next/navigation', () => ({ useRouter: jest.fn() }));
jest.mock('../../../lib/services/http', () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock('../../../lib/services/tokens', () => ({
  getAccessToken: jest.fn(), getRefreshToken: jest.fn(), clearTokens: jest.fn(), setTokens: jest.fn(),
}));

type SessionUser = NonNullable<ReturnType<typeof useAuthStore.getState>['user']>;
type HttpResponse = { data: unknown };
const staffUser: SessionUser = {
  id: 1, email: 'admin@example.com', first_name: 'Admin', last_name: 'User', role: 'customer', is_staff: true,
};
const customerUser: SessionUser = { ...staffUser, id: 2, email: 'customer@example.com', role: 'admin', is_staff: false };
const users = [{ id: 10, email: 'listed@example.com', role: 'admin', is_staff: true, is_active: true }];
const sales = [{ id: 20, email: 'buyer@example.com', city: 'Madrid', state: 'MD', postal_code: '28001' }];
const mockApi = api as jest.Mocked<typeof api>;
const mockGetAccessToken = getAccessToken as jest.Mock;
const mockGetRefreshToken = getRefreshToken as jest.Mock;
const mockClearTokens = clearTokens as jest.Mock;
const replace = jest.fn();
let serverUser: SessionUser;
let responses: Record<string, () => Promise<HttpResponse>>;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((finish) => { resolve = finish; });
  return { promise, resolve };
}

function arrangeSession(user: SessionUser | null, access = 'access') {
  mockGetAccessToken.mockReturnValue(access);
  mockGetRefreshToken.mockReturnValue('refresh');
  useAuthStore.setState({ user, accessToken: access, refreshToken: 'refresh', isAuthenticated: true });
}

function protectedRequests() {
  return mockApi.get.mock.calls.filter(([path]) => path === 'users/' || path === 'sales/');
}

describe('BackofficePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    (useRouter as jest.Mock).mockReturnValue({ replace });
    serverUser = staffUser;
    responses = {
      'validate_token/': async () => ({ data: { user: serverUser } }),
      'users/': async () => ({ data: users }),
      'sales/': async () => ({ data: sales }),
    };
    mockApi.get.mockImplementation((path) => responses[path]() as ReturnType<typeof api.get>);
    mockClearTokens.mockImplementation(() => {
      mockGetAccessToken.mockReturnValue(null);
      mockGetRefreshToken.mockReturnValue(null);
    });
    arrangeSession(staffUser);
  });

  it('redirects visitors to sign in', async () => {
    mockGetAccessToken.mockReturnValue(null);
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });

    const { container } = render(<BackofficePage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/sign-in'));
    expect(container).toBeEmptyDOMElement();
    expect(protectedRequests()).toHaveLength(0);
  });

  it('waits for session validation before requesting protected data', async () => {
    const validation = deferred<HttpResponse>();
    responses['validate_token/'] = () => validation.promise;

    render(<BackofficePage />);

    expect(screen.getByText('Checking access...')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(protectedRequests()).toHaveLength(0);
    await act(async () => validation.resolve({ data: { user: staffUser } }));
    expect(await screen.findByText('listed@example.com')).toBeInTheDocument();
  });

  it('restores a session with no cached user', async () => {
    arrangeSession(null);

    render(<BackofficePage />);

    expect(screen.getByText('Checking access...')).toBeInTheDocument();
    expect(await screen.findByText('listed@example.com')).toBeInTheDocument();
    expect(useAuthStore.getState().user?.is_staff).toBe(true);
  });

  it('denies a customer with an admin role label', async () => {
    serverUser = customerUser;
    arrangeSession(customerUser);

    render(<BackofficePage />);

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Admin access required.');
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toHaveAttribute('href', '/dashboard');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(protectedRequests()).toHaveLength(0);
  });

  it('uses the restored permission instead of cached staff status', async () => {
    serverUser = customerUser;

    render(<BackofficePage />);

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
    expect(protectedRequests()).toHaveLength(0);
  });

  it('renders protected data for staff', async () => {
    render(<BackofficePage />);

    expect(await screen.findByText('listed@example.com')).toBeInTheDocument();
    expect(screen.getByText('buyer@example.com')).toBeInTheDocument();
    expect(screen.getAllByRole('table')).toHaveLength(2);
  });

  it('shows loading while protected requests are pending', async () => {
    const userResponse = deferred<HttpResponse>();
    responses['users/'] = () => userResponse.promise;

    render(<BackofficePage />);

    expect(await screen.findByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByText('No data')).not.toBeInTheDocument();
    await act(async () => userResponse.resolve({ data: users }));
    expect(await screen.findByText('listed@example.com')).toBeInTheDocument();
  });

  it('shows access denial for a server permission rejection', async () => {
    responses['users/'] = async () => { throw { response: { status: 403 } }; };

    render(<BackofficePage />);

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.queryByText('buyer@example.com')).not.toBeInTheDocument();
  });

  it('shows a temporary failure when data cannot load', async () => {
    responses['users/'] = async () => { throw new Error('Network failed'); };

    render(<BackofficePage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load backoffice data.');
    expect(screen.queryByText('No data')).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows empty rows after successful empty responses', async () => {
    responses['users/'] = async () => ({ data: [] });
    responses['sales/'] = async () => ({ data: [] });

    render(<BackofficePage />);

    expect(await screen.findAllByText('No data')).toHaveLength(2);
  });

  it('renders fallback values in a listed user row', async () => {
    responses['users/'] = async () => ({ data: [{ ...users[0], role: '', is_staff: false, is_active: false }] });

    render(<BackofficePage />);

    const row = (await screen.findByText('listed@example.com')).closest('tr')!;
    expect(within(row).getByText('-')).toBeInTheDocument();
    expect(within(row).getAllByText('no')).toHaveLength(2);
  });

  it('clears previously loaded rows when staff permission is removed', async () => {
    render(<BackofficePage />);
    expect(await screen.findByText('listed@example.com')).toBeInTheDocument();
    serverUser = customerUser;

    act(() => useAuthStore.setState({ user: customerUser }));

    expect(screen.queryByText('listed@example.com')).not.toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('ignores an old response after the session changes', async () => {
    const oldUsers = deferred<HttpResponse>();
    responses['users/'] = () => oldUsers.promise;
    render(<BackofficePage />);
    expect(await screen.findByText('Loading...')).toBeInTheDocument();
    serverUser = customerUser;

    act(() => arrangeSession(customerUser, 'different-access'));
    await act(async () => oldUsers.resolve({ data: users }));

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument();
    expect(screen.queryByText('listed@example.com')).not.toBeInTheDocument();
  });
});
