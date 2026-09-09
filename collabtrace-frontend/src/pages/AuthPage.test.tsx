import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TOKEN_KEY } from '../api/client'
import { AuthProvider } from '../contexts/AuthContext'
import { AuthPage } from './AuthPage'

const mocks = vi.hoisted(() => ({ passwordLogin: vi.fn(), codeLogin: vi.fn(), sendCode: vi.fn(), register: vi.fn(), me: vi.fn() }))
vi.mock('../api/auth', () => ({ authApi: mocks }))

function renderPage() { return render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/auth']}><AuthProvider><Routes><Route path="/auth" element={<AuthPage/>}/><Route path="/dashboard" element={<div>Dashboard reached</div>}/></Routes></AuthProvider></MemoryRouter>) }

describe('authentication UI', () => {
  beforeEach(() => { mocks.passwordLogin.mockResolvedValue({ access_token: 'test-token', user: { id: 2, username: 'member', display_name: 'Member', role: 'MEMBER', email: null } }); mocks.codeLogin.mockResolvedValue({ access_token: 'code-token', user: { id: 2, username: 'member', display_name: 'Member', role: 'MEMBER', email: 'm@example.com' } }); mocks.sendCode.mockResolvedValue({ message: 'sent' }); mocks.register.mockResolvedValue({}); mocks.me.mockRejectedValue(new Error('none')) })
  it('logs in with identifier and stores the token in sessionStorage', async () => { const user = userEvent.setup(); renderPage(); await user.type(screen.getByLabelText('用户名 / 邮箱'), 'member'); await user.type(screen.getByLabelText('密码'), 'password'); await user.click(screen.getByRole('button', { name: /进入 CollabTrace/ })); await screen.findByText('Dashboard reached'); expect(mocks.passwordLogin).toHaveBeenCalledWith('member', 'password'); expect(sessionStorage.getItem(TOKEN_KEY)).toBe('test-token') })
  it('supports email code login and code sending', async () => { const user = userEvent.setup(); renderPage(); await user.click(screen.getByRole('button', { name: '邮箱验证码登录' })); await user.type(screen.getByLabelText('邮箱'), 'm@example.com'); await user.click(screen.getByRole('button', { name: '发送验证码' })); expect(mocks.sendCode).toHaveBeenCalledWith('m@example.com', 'LOGIN'); await user.type(screen.getByLabelText('验证码'), '123456'); await user.click(screen.getByRole('button', { name: /进入 CollabTrace/ })); await screen.findByText('Dashboard reached'); expect(mocks.codeLogin).toHaveBeenCalled() })
  it('registers without exposing or sending a role field', async () => { const user = userEvent.setup(); renderPage(); await user.click(screen.getByRole('button', { name: '注册' })); expect(screen.queryByLabelText(/role/i)).not.toBeInTheDocument(); await user.type(screen.getByLabelText('用户名'), 'new-member'); await user.type(screen.getByLabelText('邮箱'), 'new@example.com'); await user.type(screen.getByLabelText('验证码'), '123456'); await user.type(screen.getByLabelText('注册密码'), 'password1'); await user.type(screen.getByLabelText('确认密码'), 'password1'); await user.click(screen.getByRole('button', { name: /创建账号/ })); await waitFor(() => expect(mocks.register).toHaveBeenCalled()); expect(mocks.register.mock.calls[0][0]).not.toHaveProperty('role'); expect(await screen.findByText(/注册成功/)).toBeInTheDocument() })
  it('shows inline errors rather than native alerts', async () => { mocks.passwordLogin.mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'Invalid identifier or password' }, status: 401 } }); const user = userEvent.setup(); renderPage(); await user.type(screen.getByLabelText('用户名 / 邮箱'), 'bad'); await user.type(screen.getByLabelText('密码'), 'bad'); await user.click(screen.getByRole('button', { name: /进入 CollabTrace/ })); expect(await screen.findByRole('alert')).toHaveTextContent('Invalid identifier or password') })
})
