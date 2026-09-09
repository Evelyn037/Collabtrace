import { api } from './client'
import type { ManagedUser, Member, RepositoryAccess, Role } from '../types'

export const adminApi = {
  users: async () => (await api.get<ManagedUser[]>('/api/users')).data,
  updateUser: async (id: number, payload: { role?: 'ADMIN' | 'MEMBER'; is_active?: boolean; display_name?: string }) =>
    (await api.patch<ManagedUser>(`/api/users/${id}`, payload)).data,
  createMapping: async (repositoryId: number, payload: { display_name: string; github_username: string; user_id: number }) =>
    (await api.post<{ member: Member; remapped_events: number }>(`/api/repositories/${repositoryId}/members`, payload)).data,
  updateMapping: async (repositoryId: number, memberId: number, payload: { display_name?: string }) =>
    (await api.patch<{ member: Member; remapped_events: number }>(`/api/repositories/${repositoryId}/members/${memberId}`, payload)).data,
  access: async (repositoryId: number) =>
    (await api.get<RepositoryAccess[]>(`/api/repositories/${repositoryId}/access`)).data,
  updateAccess: async (repositoryId: number, userId: number, role: Role) =>
    (await api.patch<RepositoryAccess>(`/api/repositories/${repositoryId}/access/${userId}`, { role })).data,
}
