'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

import type { Blog } from '@/lib/types';
import { useBlogStore } from '@/lib/stores/blogStore';

export default function BlogDetailPage() {
  const params = useParams<{ blogId: string }>();
  const blogId = Number(params?.blogId);

  if (!Number.isFinite(blogId)) return <BlogNotFound />;

  return <BlogDetail key={blogId} blogId={blogId} />;
}

function BlogNotFound() {
  return (
    <main className="max-w-6xl mx-auto px-6 py-12">
      <p className="text-muted-foreground">Blog not found.</p>
      <Link href="/blogs" className="mt-4 inline-block text-sm text-foreground hover:underline">
        Back to blogs
      </Link>
    </main>
  );
}

function BlogDetail({ blogId }: { blogId: number }) {
  const fetchBlog = useBlogStore((s) => s.fetchBlog);
  const [blog, setBlog] = useState<Blog | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const data = await fetchBlog(blogId);
        if (active) setBlog(data);
      } catch {
        if (active) setHasError(true);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [fetchBlog, blogId, attempt]);

  if (loading) {
    return (
      <main className="max-w-6xl mx-auto px-6 py-12">
        <p className="text-muted-foreground">Loading...</p>
      </main>
    );
  }

  if (hasError) {
    return (
      <main className="max-w-6xl mx-auto px-6 py-12">
        <p className="text-foreground font-semibold">Blog unavailable</p>
        <p className="mt-2 text-muted-foreground">Could not load this post. Please try again.</p>
        <button
          type="button"
          className="mt-4 rounded-full bg-primary text-primary-foreground px-5 py-2.5 hover:bg-primary/90"
          onClick={() => {
            setLoading(true);
            setHasError(false);
            setAttempt((value) => value + 1);
          }}
        >
          Retry
        </button>
        <Link href="/blogs" className="mt-4 block text-sm text-foreground hover:underline">
          Back to blogs
        </Link>
      </main>
    );
  }

  if (!blog) return <BlogNotFound />;

  return (
    <main className="max-w-6xl mx-auto px-6 py-12">
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        {blog.image_url ? (
          <div className="relative w-full aspect-[16/9] bg-muted">
            <Image src={blog.image_url} alt={blog.title} fill className="object-cover" sizes="(max-width: 1024px) 100vw, 1024px" />
          </div>
        ) : null}

        <div className="p-6 sm:p-10">
          <p className="text-sm text-muted-foreground">{blog.category || 'Blog'}</p>
          <h1 className="text-3xl sm:text-4xl font-bold mt-2 tracking-tight">{blog.title}</h1>

          {blog.description ? (
            <p className="mt-6 text-foreground whitespace-pre-line leading-relaxed">{blog.description}</p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
