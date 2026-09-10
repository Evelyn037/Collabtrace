import { api } from './client'
import type { LoginResponse, User } from '../types'

export const authApi = {
  passwordLogin: async (identifier: string, password: string) =>
    (await api.post<LoginResponse>('/api/auth/login', { identifier, password })).data,
  register: async (payload: {
    username: string; email: string; password: string; confirm_password: string
  }) => (await api.post<User>('/api/auth/register', payload)).data,
  me: async () => (await api.get<User>('/api/auth/me')).data,
}
