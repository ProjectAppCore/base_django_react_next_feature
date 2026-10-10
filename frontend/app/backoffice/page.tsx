'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { api } from '@/lib/services/http';
import { useAuthStore } from '@/lib/stores/authStore';
import type { SaleListItem, UserListItem } from '@/lib/types';

function BackofficeSession({ accessToken }: { accessToken: string | null }) {
  const restoreUser = useAuthStore((state) => state.restoreUser);
  const [accessChecked, setAccessChecked] = useState(false);
  const [isStaff, setIsStaff] = useState(false);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [sales, setSales] = useState<SaleListItem[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [accessDenied, setAccessDenied] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      await restoreUser();
      const current = useAuthStore.getState();
      if (!active || !current.isAuthenticated || !current.user || current.accessToken !== accessToken) return;
      const permitted = current.user.is_staff === true;
      setIsStaff(permitted);
      setAccessChecked(true);
      if (!permitted) return;

      setLoading(true);
      try {
        const [usersRes, salesRes] = await Promise.all([api.get('users/'), api.get('sales/')]);
        if (!active) return;
        setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
        setSales(Array.isArray(salesRes.data) ? salesRes.data : []);
        setDataLoaded(true);
      } catch (e) {
        if (!active) return;
        setUsers([]);
        setSales([]);
        const status = (e as { response?: { status?: number } })?.response?.status;
        if (status === 403) {
          setAccessDenied(true);
        } else {
          setError('Could not load backoffice data.');
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => { active = false; };
  }, [accessToken, restoreUser]);

  if (!accessChecked) {
    return <main className="max-w-6xl mx-auto px-6 py-10">Checking access...</main>;
  }
  if (!isStaff || accessDenied) {
    return (
      <main className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold">Access denied</h1>
        <p className="mt-2 text-destructive" role="alert">Admin access required.</p>
        <Link href="/dashboard" className="mt-4 inline-block underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold">Backoffice</h1>
      <p className="mt-2 text-muted-foreground">Admin access required.</p>

      {loading ? <p className="mt-4 text-muted-foreground">Loading...</p> : null}
      {error ? <p className="mt-4 text-destructive" role="alert">{error}</p> : null}

      {dataLoaded && !loading && !error ? (
        <>
          <section className="mt-10">
            <h2 className="text-xl font-semibold">Users</h2>
            <div className="mt-4 overflow-x-auto border border-border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="text-left px-4 py-3">Email</th>
                    <th className="text-left px-4 py-3">Role</th>
                    <th className="text-left px-4 py-3">Staff</th>
                    <th className="text-left px-4 py-3">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-t border-border">
                      <td className="px-4 py-3">{u.email}</td>
                      <td className="px-4 py-3">{u.role || '-'}</td>
                      <td className="px-4 py-3">{u.is_staff ? 'yes' : 'no'}</td>
                      <td className="px-4 py-3">{u.is_active ? 'yes' : 'no'}</td>
                    </tr>
                  ))}
                  {!users.length ? (
                    <tr className="border-t border-border">
                      <td className="px-4 py-3" colSpan={4}>
                        No data
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mt-12">
            <h2 className="text-xl font-semibold">Sales</h2>
            <div className="mt-4 overflow-x-auto border border-border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="text-left px-4 py-3">Id</th>
                    <th className="text-left px-4 py-3">Email</th>
                    <th className="text-left px-4 py-3">City</th>
                    <th className="text-left px-4 py-3">State</th>
                    <th className="text-left px-4 py-3">Postal</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((s) => (
                    <tr key={s.id} className="border-t border-border">
                      <td className="px-4 py-3">{s.id}</td>
                      <td className="px-4 py-3">{s.email}</td>
                      <td className="px-4 py-3">{s.city}</td>
                      <td className="px-4 py-3">{s.state}</td>
                      <td className="px-4 py-3">{s.postal_code}</td>
                    </tr>
                  ))}
                  {!sales.length ? (
                    <tr className="border-t border-border">
                      <td className="px-4 py-3" colSpan={5}>
                        No data
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}

export default function BackofficePage() {
  const { isAuthenticated } = useRequireAuth();
  const accessToken = useAuthStore((state) => state.accessToken);
  const userId = useAuthStore((state) => state.user?.id);
  const isStaff = useAuthStore((state) => state.user?.is_staff === true);

  if (!isAuthenticated) return null;

  // A different identity or permission gets fresh state and cancels old requests.
  const sessionKey = JSON.stringify([accessToken, userId, isStaff]);
  return <BackofficeSession key={sessionKey} accessToken={accessToken} />;
}
