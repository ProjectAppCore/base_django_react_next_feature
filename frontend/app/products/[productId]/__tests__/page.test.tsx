import { describe, it, expect, beforeEach } from '@jest/globals';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useParams } from 'next/navigation';

import ProductDetailPage from '../page';
import { useCartStore } from '../../../../lib/stores/cartStore';
import { useProductStore } from '../../../../lib/stores/productStore';
import { api } from '../../../../lib/services/http';
import { mockProduct as product } from '../../../../lib/__tests__/fixtures';

jest.mock('../../../../lib/services/http', () => ({ api: { get: jest.fn() } }));
jest.mock('next/navigation', () => ({ useParams: jest.fn() }));

const mockApi = api as jest.Mocked<typeof api>;
const mockUseParams = useParams as jest.Mock;
const serverError = { isAxiosError: true, response: { status: 500 } };
const notFound = { isAxiosError: true, response: { status: 404 } };

function pendingRequest() {
  let resolve!: (value: { data: typeof product }) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<{ data: typeof product }>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe('ProductDetailPage', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    useProductStore.setState({ products: [], loading: false, error: null });
    useCartStore.setState({ items: [] });
    mockUseParams.mockReturnValue({ productId: '1' });
  });

  it('shows product not found for an invalid ID without fetching', () => {
    mockUseParams.mockReturnValue({ productId: 'nope' });

    render(<ProductDetailPage />);

    expect(screen.getByText('Product not found.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to catalog' })).toHaveAttribute('href', '/catalog');
    expect(mockApi.get).not.toHaveBeenCalled();
  });

  it('shows loading while the product request is pending', async () => {
    const request = pendingRequest();
    mockApi.get.mockReturnValueOnce(request.promise);

    render(<ProductDetailPage />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    await act(async () => { request.resolve({ data: product }); });
    expect(await screen.findByRole('heading', { name: product.title })).toBeInTheDocument();
  });

  it('renders the available product details', async () => {
    mockApi.get.mockResolvedValueOnce({ data: product });

    render(<ProductDetailPage />);

    expect(await screen.findByRole('heading', { name: product.title })).toBeInTheDocument();
    expect(screen.getByText(`$${product.price}`)).toBeInTheDocument();
    expect(screen.getByText(product.description!)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: product.title })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledWith('products/1/');
  });

  it('adds the displayed product to the cart', async () => {
    const user = userEvent.setup();
    mockApi.get.mockResolvedValueOnce({ data: product });
    render(<ProductDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'Add to cart' }));

    expect(useCartStore.getState().items).toEqual([{
      id: product.id, title: product.title, price: product.price, quantity: 1,
      gallery_urls: product.gallery_urls,
    }]);
    expect(useCartStore.getState().subtotal()).toBe(product.price);
  });

  it('renders a product without optional content for an array ID', async () => {
    mockUseParams.mockReturnValue({ productId: ['2'] });
    mockApi.get.mockResolvedValueOnce({
      data: { ...product, id: 2, title: 'Minimal Product', gallery_urls: undefined, description: '', category: '' },
    });

    render(<ProductDetailPage />);

    expect(await screen.findByRole('heading', { name: 'Minimal Product' })).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('Product')).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledWith('products/2/');
  });

  it('shows product not found after a 404 response', async () => {
    mockApi.get.mockRejectedValueOnce(notFound);

    render(<ProductDetailPage />);

    expect(await screen.findByText('Product not found.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to catalog' })).toHaveAttribute('href', '/catalog');
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it.each([
    ['server', serverError],
    ['network', new Error('Connection failed')],
  ])('shows a recoverable state after a %s failure', async (_kind, error) => {
    mockApi.get.mockRejectedValueOnce(error);

    render(<ProductDetailPage />);

    expect(await screen.findByText('Product unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to catalog' })).toHaveAttribute('href', '/catalog');
    expect(mockApi.get).toHaveBeenCalledTimes(1);
  });

  it('loads the product after an explicit retry succeeds', async () => {
    const user = userEvent.setup();
    mockApi.get.mockRejectedValueOnce(serverError);
    mockApi.get.mockResolvedValueOnce({ data: product });
    render(<ProductDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'Retry' }));

    expect(await screen.findByRole('heading', { name: product.title })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledTimes(2);
  });

  it('shows product not found after retry returns 404', async () => {
    const user = userEvent.setup();
    mockApi.get.mockRejectedValueOnce(serverError);
    mockApi.get.mockRejectedValueOnce(notFound);
    render(<ProductDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Product not found.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to catalog' })).toHaveAttribute('href', '/catalog');
    expect(mockApi.get).toHaveBeenCalledTimes(2);
  });

  it('keeps retry available after another temporary failure', async () => {
    const user = userEvent.setup();
    mockApi.get.mockRejectedValue(serverError);
    render(<ProductDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Product unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledTimes(2);
  });

  it('hides retry while its single request is pending', async () => {
    const user = userEvent.setup();
    const request = pendingRequest();
    mockApi.get.mockRejectedValueOnce(serverError);
    mockApi.get.mockReturnValueOnce(request.promise);
    render(<ProductDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'Retry' }));

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledTimes(2);
    await act(async () => { request.resolve({ data: product }); });
    expect(await screen.findByRole('heading', { name: product.title })).toBeInTheDocument();
  });

  it('ignores an obsolete product response after navigation', async () => {
    const previous = pendingRequest();
    mockApi.get.mockReturnValueOnce(previous.promise);
    mockApi.get.mockResolvedValueOnce({ data: { ...product, id: 2, title: 'Latest Product' } });
    const { rerender } = render(<ProductDetailPage />);
    mockUseParams.mockReturnValue({ productId: '2' });

    rerender(<ProductDetailPage />);
    await screen.findByRole('heading', { name: 'Latest Product' });
    await act(async () => { previous.resolve({ data: product }); });

    expect(screen.getByRole('heading', { name: 'Latest Product' })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenLastCalledWith('products/2/');
  });

  it('ignores an obsolete rejection after navigation', async () => {
    const previous = pendingRequest();
    mockApi.get.mockReturnValueOnce(previous.promise);
    mockApi.get.mockResolvedValueOnce({ data: { ...product, id: 2, title: 'Latest Product' } });
    const { rerender } = render(<ProductDetailPage />);
    mockUseParams.mockReturnValue({ productId: '2' });

    rerender(<ProductDetailPage />);
    await screen.findByRole('heading', { name: 'Latest Product' });
    await act(async () => { previous.reject(serverError); });

    expect(screen.getByRole('heading', { name: 'Latest Product' })).toBeInTheDocument();
    expect(screen.queryByText('Product unavailable')).not.toBeInTheDocument();
  });

  it('keeps the latest request loading after an obsolete completion', async () => {
    const previous = pendingRequest();
    const latest = pendingRequest();
    mockApi.get.mockReturnValueOnce(previous.promise);
    mockApi.get.mockReturnValueOnce(latest.promise);
    const { rerender } = render(<ProductDetailPage />);
    mockUseParams.mockReturnValue({ productId: '2' });

    rerender(<ProductDetailPage />);
    await act(async () => { previous.resolve({ data: product }); });

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    await act(async () => { latest.resolve({ data: { ...product, id: 2, title: 'Latest Product' } }); });
    expect(await screen.findByRole('heading', { name: 'Latest Product' })).toBeInTheDocument();
  });

  it('clears the displayed product when navigation changes to an invalid ID', async () => {
    mockApi.get.mockResolvedValueOnce({ data: product });
    const { rerender } = render(<ProductDetailPage />);
    await screen.findByRole('heading', { name: product.title });
    mockUseParams.mockReturnValue({ productId: 'invalid' });

    rerender(<ProductDetailPage />);

    expect(screen.getByText('Product not found.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add to cart' })).not.toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledTimes(1);
  });
});
