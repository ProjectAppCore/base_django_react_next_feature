'use client';

import Link from 'next/link';

import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { useAuthStore } from '@/lib/stores/authStore';

export default function DashboardPage() {
  const { isAuthenticated } = useRequireAuth();
  const signOut = useAuthStore((s) => s.signOut);
  const isStaff = useAuthStore((s) => s.user?.is_staff === true);

  if (!isAuthenticated) return null;

  return (
    <main className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-muted-foreground">Protected route (JWT required).</p>

      <div className="mt-6 flex flex-wrap gap-3">
        {isStaff ? (
          <Link className="border border-border rounded px-3 py-2 hover:bg-accent hover:text-accent-foreground" href="/backoffice">
            Backoffice
          </Link>
        ) : null}
        <button className="bg-primary text-primary-foreground rounded px-3 py-2 hover:bg-primary/90" type="button" onClick={signOut}>
          Sign out
        </button>
      </div>
    </main>
  );
}
