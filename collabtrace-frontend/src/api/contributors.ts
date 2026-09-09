import { api } from './client'
import type { Contributor, EventPage, EventType, Member, TimelinePoint } from '../types'

export const contributorApi = {
  stats: async (repositoryId: number, excludeBots = true) =>
    (await api.get<Contributor[]>(`/api/repositories/${repositoryId}/contributor-stats`, {
      params: { exclude_bots: excludeBots },
    })).data,
  detail: async (repositoryId: number, username: string) =>
    (await api.get<Contributor>(`/api/repositories/${repositoryId}/contributors/${encodeURIComponent(username)}`)).data,
  timeline: async (repositoryId: number, username: string) =>
    (await api.get<TimelinePoint[]>(`/api/repositories/${repositoryId}/contributors/${encodeURIComponent(username)}/timeline`)).data,
  events: async (repositoryId: number, username: string, eventType?: EventType, limit = 50, offset = 0) =>
    (await api.get<EventPage>(`/api/repositories/${repositoryId}/events`, {
      params: { author_login: username, event_type: eventType, limit, offset },
    })).data,
  members: async (repositoryId: number) =>
    (await api.get<Member[]>(`/api/repositories/${repositoryId}/members`)).data,
}
