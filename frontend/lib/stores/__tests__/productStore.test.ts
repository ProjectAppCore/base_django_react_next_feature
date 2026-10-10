import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useProductStore } from '../productStore';
import { api } from '../../services/http';
import { mockProducts, mockProduct } from '../../__tests__/fixtures';

jest.mock('../../services/http', () => ({
  api: {
    get: jest.fn(),
  },
}));

const mockApi = api as jest.Mocked<typeof api>;

describe('productStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset store state
    useProductStore.setState({ products: [], loading: false, error: null });
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('fetchProducts', () => {
    it('should fetch products successfully', async () => {
      mockApi.get.mockResolvedValueOnce({ data: mockProducts });

      const { result } = renderHook(() => useProductStore());

      await act(async () => {
        await result.current.fetchProducts();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.products).toEqual(mockProducts);
        expect(result.current.error).toBeNull();
      });
    });

    it('should handle non-array response', async () => {
      mockApi.get.mockResolvedValueOnce({ data: { id: 1 } });

      const { result } = renderHook(() => useProductStore());

      await act(async () => {
        await result.current.fetchProducts();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.products).toEqual([]);
        expect(result.current.error).toBeNull();
      });
    });

    it('should handle fetch error', async () => {
      mockApi.get.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useProductStore());

      await act(async () => {
        await result.current.fetchProducts();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.error).toBe('Could not load products. Is the backend running?');
        expect(result.current.products).toEqual([]);
      });
    });

    it('should set loading state during fetch', async () => {
      // Create a promise that resolves after we check the loading state
      let resolvePromise: (value: any) => void;
      const promise: Promise<any> = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockApi.get.mockImplementation(() => promise);

      const { result } = renderHook(() => useProductStore());

      act(() => {
        result.current.fetchProducts();
      });

      expect(result.current.loading).toBe(true);
      
      // Resolve the promise to clean up
      await act(async () => {
        resolvePromise!({ data: [] });
        await promise;
      });
    });
  });

  describe('fetchProduct', () => {
    it('should fetch single product successfully', async () => {
      mockApi.get.mockResolvedValueOnce({ data: mockProduct });

      const { result } = renderHook(() => useProductStore());

      let product;
      await act(async () => {
        product = await result.current.fetchProduct(1);
      });

      expect(product).toEqual(mockProduct);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('returns null after an Axios 404 response', async () => {
      mockApi.get.mockRejectedValueOnce({ isAxiosError: true, response: { status: 404 } });

      const product = await useProductStore.getState().fetchProduct(999);

      expect(product).toBeNull();
      expect(useProductStore.getState().loading).toBe(false);
      expect(useProductStore.getState().error).toBeNull();
    });

    it.each([
      ['server', { isAxiosError: true, response: { status: 500 } }],
      ['network', new Error('Connection failed')],
      ['non-Axios 404', { response: { status: 404 } }],
    ])('rejects a %s failure as recoverable', async (_kind, error) => {
      mockApi.get.mockRejectedValueOnce(error);

      await expect(useProductStore.getState().fetchProduct(1)).rejects.toBe(error);

      expect(useProductStore.getState().loading).toBe(false);
      expect(useProductStore.getState().error).toBe('Could not load product. Please try again.');
    });

    it('clears the previous detail error before a new request', async () => {
      useProductStore.setState({ error: 'Previous failure' });
      let resolveRequest!: (value: { data: typeof mockProduct }) => void;
      mockApi.get.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));

      const request = useProductStore.getState().fetchProduct(1);

      expect(useProductStore.getState().loading).toBe(true);
      expect(useProductStore.getState().error).toBeNull();
      resolveRequest({ data: mockProduct });
      await expect(request).resolves.toEqual(mockProduct);
      expect(useProductStore.getState().loading).toBe(false);
    });
  });

  describe('clearError', () => {
    it('resets error to null when clearError is called', () => {
      useProductStore.setState({ error: 'some error', products: mockProducts, loading: false });

      const { result } = renderHook(() => useProductStore());

      act(() => {
        result.current.clearError();
      });

      // Bug this catches: a clearError that wipes more than the error field
      // (e.g. `set({ error: null, products: [] })`) would still pass a null-only check.
      expect(result.current.error).toBeNull();
      expect(result.current.products).toEqual(mockProducts);
    });
  });
});
