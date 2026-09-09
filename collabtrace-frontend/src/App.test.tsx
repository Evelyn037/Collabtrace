import { AxiosError, AxiosHeaders } from 'axios'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TOKEN_KEY } from './api/client'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
import { contributionIndex, contributors, events, overview, repository, timeline, users } from './test/fixtures'
import type { Repository, RepositoryAccess, RCIWeights } from './types'

const state = vi.hoisted(() => ({ globalRole: 'MEMBER' as 'MEMBER' | 'ADMIN', repositories: [] as Repository[] }))
const mocks = vi.hoisted(() => ({ updateUser: vi.fn(), createMapping: vi.fn(), updateMapping: vi.fn(), updateAccess: vi.fn(), analyze: vi.fn(), contributionIndex: vi.fn() }))
const repoAdmin = { ...repository, id: 2, full_name: 'demo/admin', current_user_role: 'ADMIN' as const }
const repoMember = { ...repository, id: 3, full_name: 'demo/member', current_user_role: 'MEMBER' as const }
const accessEntries: RepositoryAccess[] = [
  { user_id: 1, username: 'member', display_name: 'Member', email: null, is_active: true, role: 'ADMIN', explicit: true },
  { user_id: 2, username: 'bob', display_name: 'Bob', email: 'bob@example.com', is_active: true, role: 'MEMBER', explicit: false },
]

vi.mock('./api/auth', () => ({ authApi: { me: vi.fn(async () => ({ id: 1, username: 'member', display_name: 'Member', role: state.globalRole, email: null })) } }))
vi.mock('./api/repositories', () => ({ repositoryApi: {
  list: vi.fn(async () => state.repositories),
  detail: vi.fn(async (id: number) => ({ ...state.repositories.find((item) => item.id === id), event_count: 57, member_count: 1 })),
  overview: vi.fn(async () => overview), contributionIndex: mocks.contributionIndex, timeline: vi.fn(async () => timeline), syncs: vi.fn(async () => []), sync: vi.fn(), analyze: mocks.analyze,
} }))
vi.mock('./api/contributors', () => ({ contributorApi: { stats: vi.fn(async () => contributors), detail: vi.fn(async () => contributors[0]), timeline: vi.fn(async () => timeline), events: vi.fn(async () => ({ total: events.length, items: events })), members: vi.fn(async () => []) } }))
vi.mock('./api/admin', () => ({ adminApi: {
  users: vi.fn(async () => users), updateUser: mocks.updateUser, createMapping: mocks.createMapping, updateMapping: mocks.updateMapping,
  access: vi.fn(async () => accessEntries), updateAccess: mocks.updateAccess,
} }))

function renderApp(path: string, selectedId = state.repositories[0]?.id) {
  sessionStorage.setItem(TOKEN_KEY, 'session-token')
  if (selectedId) sessionStorage.setItem('collabtrace_repository_id', String(selectedId))
  return render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[path]}><AuthProvider><App/></AuthProvider></MemoryRouter>)
}

function conflict(message: string) {
  return new AxiosError('Conflict', 'ERR_BAD_REQUEST', undefined, undefined, {
    config: { headers: new AxiosHeaders() }, data: { detail: message }, headers: new AxiosHeaders(), status: 409, statusText: 'Conflict',
  })
}

function forbidden(message: string) {
  return new AxiosError('Forbidden', 'ERR_BAD_REQUEST', undefined, undefined, {
    config: { headers: new AxiosHeaders() }, data: { detail: message }, headers: new AxiosHeaders(), status: 403, statusText: 'Forbidden',
  })
}

describe('repository-scoped RBAC and navigation', () => {
  beforeEach(() => {
    sessionStorage.clear(); state.globalRole = 'MEMBER'; state.repositories = [repoAdmin, repoMember]
    accessEntries[0].role = 'ADMIN'; accessEntries[0].explicit = true
    accessEntries[1].role = 'MEMBER'; accessEntries[1].explicit = false
    mocks.updateAccess.mockReset().mockImplementation(async (_repositoryId, userId, role) => ({ ...accessEntries.find((entry) => entry.user_id === userId)!, role, explicit: true }))
    mocks.updateUser.mockReset().mockResolvedValue(undefined)
    mocks.analyze.mockReset()
    mocks.contributionIndex.mockReset().mockImplementation(async (_id: number, weights?: RCIWeights) => ({ ...contributionIndex, mode: weights ? 'CUSTOM_WEIGHTS' : 'RESEARCH_BASELINE', requested_weights: weights || contributionIndex.requested_weights }))
  })

  it('lets a global MEMBER analyze while a MEMBER repository hides write controls', async () => {
    renderApp('/dashboard', repoMember.id)
    expect(await screen.findByText('团队贡献概览')).toBeInTheDocument()
    const navigation = screen.getByRole('navigation', { name: '主导航' })
    expect(within(navigation).getByRole('link', { name: /情况总览/ })).toBeInTheDocument()
    expect(within(navigation).queryByRole('link', { name: /仪表盘/ })).not.toBeInTheDocument()
    expect(within(screen.getByRole('banner')).queryByRole('button', { name: /分析 Repository/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /分析 Repository/ })).toHaveLength(1)
    expect(screen.getByText('MEMBER', { selector: '.repository-role' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Sync Now/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /管理中心/ })).not.toBeInTheDocument()
  })

  it('offers the existing dashboard instead of a technical error when MEMBER analyze is read-only', async () => {
    mocks.analyze.mockRejectedValueOnce(forbidden('Repository administrator permission is required'))
    const user = userEvent.setup(); renderApp('/dashboard', repoMember.id)
    await user.click((await screen.findAllByRole('button', { name: /分析 Repository/ }))[0])
    fireEvent.change(screen.getByPlaceholderText(/github.com/), { target: { value: 'https://github.com/demo/member.git/' } })
    await user.click(screen.getByRole('button', { name: /^Analyze/ }))
    await waitFor(() => expect(mocks.analyze).toHaveBeenCalledWith('https://github.com/demo/member.git/'))
    expect(await screen.findByRole('dialog')).toHaveTextContent('This repository has already been analyzed.')
    expect(screen.getByText(/read-only access/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Open Dashboard/ })).toBeInTheDocument()
  })

  it('shows Admin Center and Access for a repository ADMIN even when global role is MEMBER', async () => {
    renderApp('/admin?tab=access', repoAdmin.id)
    expect(await screen.findByRole('heading', { name: '管理中心' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /管理中心/ })).toBeInTheDocument()
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['Repositories', 'Member Mapping', 'Access', 'Sync History'])
    expect(screen.queryByRole('tab', { name: 'System / Users' })).not.toBeInTheDocument()
    expect(await screen.findByText('Repository Role')).toBeInTheDocument()
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.queryByText('System Role')).not.toBeInTheDocument()
    await screen.findByText('@bob')
  })

  it('retains the Analyze Repository action in the Admin repository tab', async () => {
    renderApp('/admin', repoAdmin.id)
    expect(await screen.findByRole('heading', { name: '已分析 Repository' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /分析 Repository/ })).toBeInTheDocument()
  })

  it('keeps System Users out of the profile menu for a repository ADMIN with standard system role', async () => {
    const user = userEvent.setup(); renderApp('/dashboard', repoAdmin.id)
    expect(await screen.findByRole('link', { name: /管理中心/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '用户菜单' })).toHaveTextContent('STANDARD USER')
    await user.click(screen.getByRole('button', { name: '用户菜单' }))
    expect(screen.queryByRole('menuitem', { name: /System Users/ })).not.toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Logout' })).toBeInTheDocument()
  })

  it('allows only a System Admin into /system/users even when the selected repository is MEMBER', async () => {
    const standardUserView = renderApp('/system/users', repoMember.id)
    expect(await screen.findByText('没有操作权限')).toBeInTheDocument()
    standardUserView.unmount()

    state.globalRole = 'ADMIN'
    renderApp('/system/users', repoMember.id)
    expect(await screen.findByRole('heading', { name: '系统账号' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /管理中心/ })).not.toBeInTheDocument()
    expect(screen.getByText('SYSTEM ADMIN', { selector: '.system-hero-mark span' })).toBeInTheDocument()
    expect(screen.getByText('STANDARD USER', { selector: '.system-role-badge' })).toBeInTheDocument()
    expect(screen.queryByText('Repository Role')).not.toBeInTheDocument()
    expect(screen.queryByText('Source')).not.toBeInTheDocument()
  })

  it('opens System Users from the System Admin profile menu and stays there while switching repositories', async () => {
    state.globalRole = 'ADMIN'
    const user = userEvent.setup(); renderApp('/dashboard', repoMember.id)
    expect(await screen.findByText('团队贡献概览')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /管理中心/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '用户菜单' }))
    await user.click(screen.getByRole('menuitem', { name: /System Users/ }))
    expect(await screen.findByRole('heading', { name: '系统账号' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('选择 Repository'), String(repoAdmin.id))
    expect(screen.getByRole('heading', { name: '系统账号' })).toBeInTheDocument()
    expect(screen.getByText('ADMIN', { selector: '.repository-role' })).toBeInTheDocument()
  })

  it('supports profile menu focus, arrow keys, Escape, and outside-click close', async () => {
    state.globalRole = 'ADMIN'
    const user = userEvent.setup(); renderApp('/dashboard', repoMember.id)
    const trigger = await screen.findByRole('button', { name: '用户菜单' })
    await user.click(trigger)
    const menu = screen.getByRole('menu')
    const systemUsers = within(menu).getByRole('menuitem', { name: /System Users/ })
    const logout = within(menu).getByRole('menuitem', { name: 'Logout' })
    expect(systemUsers).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(logout).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
    await user.click(trigger)
    fireEvent.mouseDown(document.body)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('updates a System Role label without changing the selected Repository Role', async () => {
    state.globalRole = 'ADMIN'
    const user = userEvent.setup(); renderApp('/system/users', repoMember.id)
    const memberRow = await screen.findByRole('button', { name: /Member.*STANDARD USER.*Active/ })
    await user.click(memberRow)
    await user.selectOptions(screen.getByLabelText('System Role'), 'ADMIN')
    await user.click(screen.getByRole('button', { name: '保存系统账号' }))
    await waitFor(() => expect(mocks.updateUser).toHaveBeenCalledWith(2, { role: 'ADMIN', is_active: true }))
    expect(screen.getByText('MEMBER', { selector: '.repository-role' })).toBeInTheDocument()
  })

  it('updates controls immediately when switching ADMIN repository to MEMBER repository', async () => {
    const user = userEvent.setup(); renderApp('/dashboard', repoAdmin.id)
    expect(await screen.findByRole('button', { name: /Sync Now/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /管理中心/ })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('选择 Repository'), String(repoMember.id))
    await waitFor(() => expect(screen.queryByRole('button', { name: /Sync Now/ })).not.toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /管理中心/ })).not.toBeInTheDocument()
    expect(screen.getByText('MEMBER', { selector: '.repository-role' })).toBeInTheDocument()
    expect(screen.getByText('团队贡献概览')).toBeInTheDocument()
  })

  it('protects /admin with the selected repository role rather than global role', async () => {
    state.globalRole = 'ADMIN'; renderApp('/admin', repoMember.id)
    expect(await screen.findByText('没有操作权限')).toBeInTheDocument()
  })

  it('uses situation-overview copy on 403 and keeps the dashboard destination', async () => {
    const user = userEvent.setup(); renderApp('/403', repoMember.id)
    expect(await screen.findByRole('heading', { name: '没有操作权限' })).toBeInTheDocument()
    const returnLink = screen.getByRole('link', { name: /返回情况总览/ })
    expect(returnLink).toHaveAttribute('href', '/dashboard')
    expect(screen.queryByText('返回仪表盘')).not.toBeInTheDocument()
    await user.click(returnLink)
    expect(await screen.findByText('团队贡献概览')).toBeInTheDocument()
  })

  it('promotes a MEMBER through the Access API', async () => {
    const user = userEvent.setup(); renderApp('/admin?tab=access', repoAdmin.id)
    await user.selectOptions(await screen.findByLabelText('Repository role for bob'), 'ADMIN')
    await waitFor(() => expect(mocks.updateAccess).toHaveBeenCalledWith(repoAdmin.id, 2, 'ADMIN'))
    expect(screen.getByRole('button', { name: '用户菜单' })).toHaveTextContent('STANDARD USER')
  })

  it('demotes an additional ADMIN through the Access API', async () => {
    accessEntries[1].role = 'ADMIN'; accessEntries[1].explicit = true
    const user = userEvent.setup(); renderApp('/admin?tab=access', repoAdmin.id)
    await user.selectOptions(await screen.findByLabelText('Repository role for bob'), 'MEMBER')
    await waitFor(() => expect(mocks.updateAccess).toHaveBeenCalledWith(repoAdmin.id, 2, 'MEMBER'))
  })

  it('shows last-administrator protection feedback from the backend', async () => {
    mocks.updateAccess.mockRejectedValueOnce(conflict('Repository must have at least one administrator'))
    const user = userEvent.setup(); renderApp('/admin?tab=access', repoAdmin.id)
    await user.selectOptions(await screen.findByLabelText('Repository role for member'), 'MEMBER')
    expect(await screen.findByText('Repository must have at least one administrator')).toBeInTheDocument()
  })

  it('selects a newly created repository whose creator role is ADMIN', async () => {
    const created = { ...repository, id: 9, full_name: 'demo/new', current_user_role: 'ADMIN' as const }
    mocks.analyze.mockImplementation(async () => {
      state.repositories = [...state.repositories, created]
      return { repository: created, created: true, sync: { repository_id: 9, repository: 'demo/new', status: 'SUCCESS', fetched: 1, inserted: 1, updated: 0, unchanged: 0, mapped: 0, unmapped: 1, started_at: '', finished_at: '' }, analysis_scope: { max_pages: 1, max_prs_for_reviews: 5, scope_limited: true } }
    })
    const user = userEvent.setup(); renderApp('/dashboard', repoMember.id)
    await user.click((await screen.findAllByRole('button', { name: /分析 Repository/ }))[0])
    await user.type(screen.getByPlaceholderText(/github.com/), 'demo/new')
    await user.click(screen.getByRole('button', { name: /^Analyze/ }))
    expect(await screen.findByText('Analysis complete')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /打开仪表盘/ }))
    await waitFor(() => expect(screen.getByText('ADMIN', { selector: '.repository-role' })).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Sync Now/ })).toBeInTheDocument()
  })

  it('opens RCI methodology, applies personal weights, and explains a Quick View', async () => {
    const user = userEvent.setup(); renderApp('/dashboard', repoAdmin.id)
    await screen.findByText('Research Baseline')
    await user.click(screen.getByRole('button', { name: /Methodology/ }))
    expect(screen.getByRole('dialog')).toHaveTextContent('RCI Methodology · RCI_V1')
    expect(screen.getByRole('dialog')).toHaveTextContent('not a measure of ability')
    await user.click(screen.getByRole('button', { name: '关闭' }))
    await user.click(screen.getByRole('button', { name: /Weights/ }))
    await user.clear(screen.getByLabelText('Code Implementation weight'))
    await user.type(screen.getByLabelText('Code Implementation weight'), '7')
    await user.click(screen.getByRole('button', { name: 'Apply weights' }))
    await waitFor(() => expect(mocks.contributionIndex).toHaveBeenLastCalledWith(repoAdmin.id, { code: 7, pr: 1, issue: 1, review: 1 }))
    expect(await screen.findByText('Custom Weights')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /查看 王五/ }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Activity Events')
    await user.click(screen.getByRole('button', { name: /Why this RCI/ }))
    expect(screen.getByRole('region', { name: 'Why this RCI' })).toHaveTextContent('effective commits')
  })
})
