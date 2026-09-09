import { api } from './client'
import type { LoginResponse, User } from '../types'

export const authApi = {
  passwordLogin: async (identifier: string, password: string) =>
    (await api.post<LoginResponse>('/api/auth/login', { identifier, password })).data,
  codeLogin: async (email: string, verification_code: string) =>
    (await api.post<LoginResponse>('/api/auth/login/code', { email, verification_code })).data,
  sendCode: async (email: string, purpose: 'LOGIN' | 'REGISTER') =>
    (await api.post<{ message: string }>('/api/auth/verification/send', { email, purpose })).data,
  register: async (payload: {
    username: string; email: string; verification_code: string
    password: string; confirm_password: string
  }) => (await api.post<User>('/api/auth/register', payload)).data,
  me: async () => (await api.get<User>('/api/auth/me')).data,
}
