import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { contributors, events, timeline } from '../test/fixtures'
import { ContributorPage } from './ContributorPage'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), stats: vi.fn(), timeline: vi.fn(), events: vi.fn() }))
vi.mock('../api/contributors', () => ({ contributorApi: { ...mocks } }))

function renderPage() {
  mocks.detail.mockResolvedValue(contributors[0]); mocks.stats.mockResolvedValue(contributors); mocks.timeline.mockResolvedValue(timeline); mocks.events.mockResolvedValue({ total: events.length, items: events })
  return render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/repositories/2/contributors/person-1']}><Routes><Route path="/repositories/:repositoryId/contributors/:githubUsername" element={<ContributorPage/>}/></Routes></MemoryRouter>)
}

describe('contributor detail', () => {
  it('renders stats, activity rank, composition, timeline, and evidence', async () => { renderPage(); expect(await screen.findByRole('heading', { name: '王五' })).toBeInTheDocument(); expect(screen.getByText('Activity Rank')).toBeInTheDocument(); expect(screen.getByText('活动构成')).toBeInTheDocument(); expect(screen.getByText('Contributor Timeline')).toBeInTheDocument(); expect(screen.getByText('Trace the work')).toBeInTheDocument() })
  it('uses safe GitHub links and never invents a link for null URLs', async () => { renderPage(); const links = await screen.findAllByRole('link', { name: /View on GitHub/ }); expect(links).toHaveLength(1); expect(links[0]).toHaveAttribute('href', events[0].github_url); expect(links[0]).toHaveAttribute('target', '_blank'); expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer'); expect(screen.getByText('Evidence link unavailable')).toBeInTheDocument() })
  it('filters evidence by the selected event type', async () => { const user = userEvent.setup(); renderPage(); await screen.findByText('Trace the work'); await user.click(screen.getByRole('button', { name: 'Issue' })); await waitFor(() => expect(mocks.events).toHaveBeenLastCalledWith(2, 'person-1', 'ISSUE', 20, 0)) })
  it('changes the route from the contributor selector', async () => { const user = userEvent.setup(); renderPage(); const selector = await screen.findByLabelText('切换 Contributor'); await user.selectOptions(selector, 'person-2'); await waitFor(() => expect(mocks.detail).toHaveBeenCalledWith(2, 'person-2')) })
  it('shows a timeline empty state instead of fake chart data', async () => { mocks.detail.mockResolvedValue(contributors[0]); mocks.stats.mockResolvedValue(contributors); mocks.timeline.mockResolvedValue([]); mocks.events.mockResolvedValue({ total: 0, items: [] }); render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/repositories/2/contributors/person-1']}><Routes><Route path="/repositories/:repositoryId/contributors/:githubUsername" element={<ContributorPage/>}/></Routes></MemoryRouter>); expect(await screen.findByText('暂无时间线数据')).toBeInTheDocument(); expect(screen.getByText('暂无贡献证据')).toBeInTheDocument() })
})
