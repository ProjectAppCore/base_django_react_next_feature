'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

import type { Product } from '@/lib/types';
import { useCartStore } from '@/lib/stores/cartStore';
import { useProductStore } from '@/lib/stores/productStore';

export default function ProductDetailPage() {
  const params = useParams<{ productId: string | string[] }>();
  const productIdParam = params?.productId;
  const productId = Array.isArray(productIdParam) ? productIdParam[0] : productIdParam;
  const numericProductId = Number(productId);
  const hasValidProductId = Number.isFinite(numericProductId);

  if (!hasValidProductId) return <ProductNotFound />;
  return <ProductDetail key={numericProductId} productId={numericProductId} />;
}

function ProductNotFound() {
  return (
    <main className="max-w-6xl mx-auto px-6 py-12">
      <p className="text-muted-foreground">Product not found.</p>
      <Link href="/catalog" className="mt-4 inline-block text-sm text-foreground hover:underline">
        Back to catalog
      </Link>
    </main>
  );
}

function ProductDetail({ productId }: { productId: number }) {
  const fetchProduct = useProductStore((s) => s.fetchProduct);
  const addToCart = useCartStore((s) => s.addToCart);
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const data = await fetchProduct(productId);
        if (active) setProduct(data);
      } catch {
        if (active) setHasError(true);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [fetchProduct, productId, attempt]);

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
        <p className="text-foreground font-semibold">Product unavailable</p>
        <p className="mt-2 text-muted-foreground">Could not load this product. Please try again.</p>
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
        <Link href="/catalog" className="mt-4 block text-sm text-foreground hover:underline">
          Back to catalog
        </Link>
      </main>
    );
  }

  if (!product) return <ProductNotFound />;

  const gallery = product.gallery_urls || [];

  return (
    <main className="max-w-6xl mx-auto px-6 py-12">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <section>
          <div className="grid grid-cols-2 gap-4">
            {gallery.length ? (
              gallery.slice(0, 4).map((url) => (
                <div key={url} className="relative w-full aspect-square bg-muted rounded-2xl overflow-hidden">
                  <Image src={url} alt={product.title} fill className="object-cover" sizes="(max-width: 768px) 100vw, 50vw" />
                </div>
              ))
            ) : (
              <div className="w-full aspect-square bg-muted rounded-2xl" />
            )}
          </div>
        </section>

        <aside className="bg-card border border-border rounded-2xl p-6 h-fit">
          <p className="text-sm text-muted-foreground">{product.category || 'Product'}</p>
          <h1 className="text-3xl font-bold mt-2 tracking-tight">{product.title}</h1>
          <p className="mt-3 text-2xl font-semibold">${product.price}</p>

          {product.description ? (
            <p className="mt-6 text-foreground whitespace-pre-line leading-relaxed">{product.description}</p>
          ) : null}

          <button
            className="mt-8 bg-primary text-primary-foreground rounded-full px-5 py-3 w-full hover:bg-primary/90"
            type="button"
            onClick={() => addToCart(product, 1)}
          >
            Add to cart
          </button>

          <p className="mt-3 text-xs text-muted-foreground">Secure checkout. Fast delivery.</p>
        </aside>
      </div>
    </main>
  );
}
