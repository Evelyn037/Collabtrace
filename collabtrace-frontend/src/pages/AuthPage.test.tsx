import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TOKEN_KEY } from '../api/client'
import { AuthProvider } from '../contexts/AuthContext'
import { AuthPage } from './AuthPage'

const mocks = vi.hoisted(() => ({ passwordLogin: vi.fn(), register: vi.fn(), me: vi.fn() }))
vi.mock('../api/auth', () => ({ authApi: mocks }))

function renderPage() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/auth']}>
      <AuthProvider>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/dashboard" element={<div>Dashboard reached</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('password-only authentication UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mocks.passwordLogin.mockResolvedValue({
      access_token: 'test-token',
      user: { id: 2, username: 'member', display_name: 'Member', role: 'MEMBER', email: 'm@example.com' },
    })
    mocks.register.mockResolvedValue({})
    mocks.me.mockRejectedValue(new Error('none'))
  })

  it.each(['member', 'm@example.com'])('logs in with identifier %s and stores the token', async (identifier) => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('昵称或邮箱'), identifier)
    await user.type(screen.getByLabelText('密码'), 'password')
    await user.click(screen.getByRole('button', { name: /进入 CollabTrace/ }))
    await screen.findByText('Dashboard reached')
    expect(mocks.passwordLogin).toHaveBeenCalledWith(identifier, 'password')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('test-token')
  })

  it('shows the four registration fields and no verification controls', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '注册' }))
    expect(screen.getByLabelText('昵称')).toBeInTheDocument()
    expect(screen.getByLabelText('邮箱')).toBeInTheDocument()
    expect(screen.getByLabelText('注册密码')).toBeInTheDocument()
    expect(screen.getByLabelText('确认密码')).toBeInTheDocument()
    expect(screen.queryByText(/验证码/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /发送|重新发送/ })).not.toBeInTheDocument()
  })

  it('registers without verification or role fields', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '注册' }))
    await user.type(screen.getByLabelText('昵称'), 'new-member')
    await user.type(screen.getByLabelText('邮箱'), 'new@example.com')
    await user.type(screen.getByLabelText('注册密码'), 'password1')
    await user.type(screen.getByLabelText('确认密码'), 'password1')
    await user.click(screen.getByRole('button', { name: /创建账号/ }))
    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith({
      username: 'new-member',
      email: 'new@example.com',
      password: 'password1',
      confirm_password: 'password1',
    }))
    expect(mocks.register.mock.calls[0][0]).not.toHaveProperty('role')
    expect(mocks.register.mock.calls[0][0]).not.toHaveProperty('verification_code')
    expect(await screen.findByText(/注册成功/)).toBeInTheDocument()
  })

  it('rejects a password mismatch before calling the API', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: '注册' }))
    await user.type(screen.getByLabelText('昵称'), 'new-member')
    await user.type(screen.getByLabelText('邮箱'), 'new@example.com')
    await user.type(screen.getByLabelText('注册密码'), 'password1')
    await user.type(screen.getByLabelText('确认密码'), 'password2')
    await user.click(screen.getByRole('button', { name: /创建账号/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('两次输入的密码不一致。')
    expect(mocks.register).not.toHaveBeenCalled()
  })

  it('shows inline errors rather than native alerts', async () => {
    mocks.passwordLogin.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: 'Invalid identifier or password' }, status: 401 },
    })
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('昵称或邮箱'), 'bad')
    await user.type(screen.getByLabelText('密码'), 'bad')
    await user.click(screen.getByRole('button', { name: /进入 CollabTrace/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid identifier or password')
  })
})
