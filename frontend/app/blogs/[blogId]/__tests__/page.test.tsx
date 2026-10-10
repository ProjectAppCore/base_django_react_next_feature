import { describe, it, expect, beforeEach } from '@jest/globals';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useParams } from 'next/navigation';

import BlogDetailPage from '../page';
import { useBlogStore } from '../../../../lib/stores/blogStore';
import { api } from '../../../../lib/services/http';

jest.mock('../../../../lib/services/http', () => ({
  api: { get: jest.fn() },
}));

jest.mock('next/navigation', () => ({ useParams: jest.fn() }));

const mockUseParams = useParams as jest.Mock;
const mockApi = api as jest.Mocked<typeof api>;
const blog = {
  id: 1,
  title: 'Test Blog',
  category: 'Tips',
  description: 'Some blog description',
  image_url: 'http://example.com/blog.jpg',
};

describe('BlogDetailPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useBlogStore.setState({ blogs: [], loading: false, error: null });
    mockUseParams.mockReturnValue({ blogId: '1' });
  });

  it('shows blog not found when blogId is invalid', () => {
    mockUseParams.mockReturnValue({ blogId: 'abc' });

    render(<BlogDetailPage />);

    expect(screen.getByText('Blog not found.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to blogs' })).toHaveAttribute('href', '/blogs');
    expect(mockApi.get).not.toHaveBeenCalled();
  });

  it('shows loading while the blog request is pending', async () => {
    let resolveRequest!: (value: { data: typeof blog }) => void;
    mockApi.get.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));

    render(<BlogDetailPage />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    await act(async () => { resolveRequest({ data: blog }); });
    expect(await screen.findByRole('heading', { name: blog.title })).toBeInTheDocument();
  });

  it('renders blog content when available', async () => {
    mockApi.get.mockResolvedValueOnce({ data: blog });

    render(<BlogDetailPage />);

    expect(await screen.findByRole('heading', { name: blog.title })).toBeInTheDocument();
    expect(screen.getByText(blog.description)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: blog.title })).toBeInTheDocument();
  });

  it('handles blogs without image or description', async () => {
    mockApi.get.mockResolvedValueOnce({
      data: { ...blog, title: 'Text Only Blog', category: '', description: '', image_url: '' },
    });

    render(<BlogDetailPage />);

    expect(await screen.findByRole('heading', { name: 'Text Only Blog' })).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('shows blog not found after a 404 response', async () => {
    mockApi.get.mockRejectedValueOnce({ isAxiosError: true, response: { status: 404 } });

    render(<BlogDetailPage />);

    expect(await screen.findByText('Blog not found.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to blogs' })).toHaveAttribute('href', '/blogs');
  });

  it.each([
    ['server', { isAxiosError: true, response: { status: 500 } }],
    ['network', new Error('Connection failed')],
  ])('shows a recoverable error after a %s failure', async (_kind, error) => {
    mockApi.get.mockRejectedValueOnce(error);

    render(<BlogDetailPage />);

    expect(await screen.findByText('Blog unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to blogs' })).toHaveAttribute('href', '/blogs');
  });

  it('loads the blog after an explicit retry', async () => {
    const user = userEvent.setup();
    mockApi.get.mockRejectedValueOnce({ isAxiosError: true, response: { status: 500 } });
    mockApi.get.mockResolvedValueOnce({ data: blog });
    render(<BlogDetailPage />);
    const retry = await screen.findByRole('button', { name: 'Retry' });

    await user.click(retry);

    expect(await screen.findByRole('heading', { name: blog.title })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenCalledTimes(2);
  });

  it('ignores the previous blog response after navigation', async () => {
    let resolvePrevious!: (value: { data: typeof blog }) => void;
    mockApi.get.mockReturnValueOnce(new Promise((resolve) => { resolvePrevious = resolve; }));
    mockApi.get.mockResolvedValueOnce({ data: { ...blog, id: 2, title: 'Latest Blog' } });
    const { rerender } = render(<BlogDetailPage />);
    mockUseParams.mockReturnValue({ blogId: '2' });

    rerender(<BlogDetailPage />);
    await screen.findByRole('heading', { name: 'Latest Blog' });
    await act(async () => { resolvePrevious({ data: blog }); });

    expect(screen.getByRole('heading', { name: 'Latest Blog' })).toBeInTheDocument();
    expect(mockApi.get).toHaveBeenLastCalledWith('blogs/2/');
  });
});
