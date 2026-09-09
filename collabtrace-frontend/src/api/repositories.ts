import { api } from './client'
import type { AnalysisResult, ContributionIndex, Overview, Repository, RCIWeights, SyncRecord, SyncResult, TimelinePoint } from '../types'

export const repositoryApi = {
  list: async () => (await api.get<Repository[]>('/api/repositories')).data,
  detail: async (id: number) => (await api.get<Repository>(`/api/repositories/${id}`)).data,
  analyze: async (repository: string) =>
    (await api.post<AnalysisResult>('/api/repositories/analyze', { repository })).data,
  sync: async (id: number) => (await api.post<SyncResult>(`/api/repositories/${id}/sync`)).data,
  overview: async (id: number) => (await api.get<Overview>(`/api/repositories/${id}/overview`)).data,
  contributionIndex: async (id: number, weights?: RCIWeights) => (await api.get<ContributionIndex>(
    `/api/repositories/${id}/contribution-index`,
    { params: weights ? {
      weight_code: weights.code, weight_pr: weights.pr,
      weight_issue: weights.issue, weight_review: weights.review,
    } : undefined },
  )).data,
  timeline: async (id: number) =>
    (await api.get<TimelinePoint[]>(`/api/repositories/${id}/timeline`)).data,
  syncs: async (id: number) => (await api.get<SyncRecord[]>(`/api/repositories/${id}/syncs`)).data,
}
