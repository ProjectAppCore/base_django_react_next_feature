import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useBlogStore } from '../blogStore';
import { api } from '../../services/http';
import { mockBlogs, mockBlog } from '../../__tests__/fixtures';

jest.mock('../../services/http', () => ({
  api: {
    get: jest.fn(),
  },
}));

const mockApi = api as jest.Mocked<typeof api>;

describe('blogStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset store state
    useBlogStore.setState({ blogs: [], loading: false, error: null });
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  describe('fetchBlogs', () => {
    it('should fetch blogs successfully', async () => {
      mockApi.get.mockResolvedValueOnce({ data: mockBlogs });

      const { result } = renderHook(() => useBlogStore());

      await act(async () => {
        await result.current.fetchBlogs();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.blogs).toEqual(mockBlogs);
        expect(result.current.error).toBeNull();
      });
    });

    it('should handle non-array response', async () => {
      mockApi.get.mockResolvedValueOnce({ data: { id: 1 } });

      const { result } = renderHook(() => useBlogStore());

      await act(async () => {
        await result.current.fetchBlogs();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.blogs).toEqual([]);
        expect(result.current.error).toBeNull();
      });
    });

    it('should handle fetch error', async () => {
      mockApi.get.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useBlogStore());

      await act(async () => {
        await result.current.fetchBlogs();
      });

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
        expect(result.current.error).toBe('Could not load blogs. Is the backend running?');
        expect(result.current.blogs).toEqual([]);
      });
    });

    it('should set loading state during fetch', async () => {
      // Create a promise that resolves after we check the loading state
      let resolvePromise: (value: any) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      
      mockApi.get.mockImplementation(() => promise);

      const { result } = renderHook(() => useBlogStore());

      act(() => {
        result.current.fetchBlogs();
      });

      expect(result.current.loading).toBe(true);
      
      // Resolve the promise to clean up
      await act(async () => {
        resolvePromise!({ data: [] });
        await promise;
      });
    });
  });

  describe('fetchBlog', () => {
    it('should fetch single blog successfully', async () => {
      mockApi.get.mockResolvedValueOnce({ data: mockBlog });

      const { result } = renderHook(() => useBlogStore());

      let blog;
      await act(async () => {
        blog = await result.current.fetchBlog(1);
      });

      expect(blog).toEqual(mockBlog);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('returns null for a missing blog', async () => {
      mockApi.get.mockRejectedValueOnce({ isAxiosError: true, response: { status: 404 } });

      const { result } = renderHook(() => useBlogStore());

      let blog;
      await act(async () => {
        blog = await result.current.fetchBlog(999);
      });

      expect(blog).toBeNull();
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it.each([
      ['server', { isAxiosError: true, response: { status: 500 } }],
      ['network', new Error('Connection failed')],
    ])('rejects a %s failure after ending loading', async (_kind, error) => {
      mockApi.get.mockRejectedValueOnce(error);

      await expect(useBlogStore.getState().fetchBlog(1)).rejects.toBe(error);

      expect(useBlogStore.getState().loading).toBe(false);
      expect(useBlogStore.getState().error).toBe('Could not load blog. Please try again.');
    });

    it('marks the detail request as loading until it completes', async () => {
      let resolveRequest!: (value: { data: typeof mockBlog }) => void;
      mockApi.get.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));

      const request = useBlogStore.getState().fetchBlog(1);

      expect(useBlogStore.getState().loading).toBe(true);
      resolveRequest({ data: mockBlog });
      await expect(request).resolves.toEqual(mockBlog);
      expect(useBlogStore.getState().loading).toBe(false);
    });
  });

  describe('clearError', () => {
    it('resets error to null when clearError is called', () => {
      useBlogStore.setState({ error: 'some error', blogs: mockBlogs, loading: false });

      const { result } = renderHook(() => useBlogStore());

      act(() => {
        result.current.clearError();
      });

      // Bug this catches: a clearError that wipes more than the error field
      // (e.g. `set({ error: null, blogs: [] })`) would still pass a null-only check.
      expect(result.current.error).toBeNull();
      expect(result.current.blogs).toEqual(mockBlogs);
    });
  });
});
