export type Role = 'ADMIN' | 'MEMBER'
export type EventType = 'COMMIT' | 'PULL_REQUEST' | 'ISSUE' | 'REVIEW'

export interface User {
  id: number; username: string; display_name: string; role: Role; email: string | null
}
export interface ManagedUser extends User {
  is_active: boolean; created_at: string; email_verified: boolean | null
}
export interface LoginResponse { access_token: string; token_type: 'bearer'; expires_in: number; user: User }
export interface Repository {
  id: number; owner: string; name: string; full_name: string; github_repo_id: number
  html_url: string; description: string | null; default_branch: string; is_private: boolean
  last_sync_at: string | null; created_at: string; updated_at: string
  current_user_role: Role
  member_count?: number; event_count?: number
}
export interface Totals { events: number; commits: number; pull_requests: number; issues: number; reviews: number }
export interface Overview {
  repository: Repository; totals: Totals; members: number; mapped_events: number
  unmapped_events: number; last_sync_at: string | null
}
export interface Contributor {
  github_username: string; member_id: number | null; user_id: number | null
  display_name: string; is_mapped: boolean; is_bot: boolean; rank: number
  total_events: number; commits: number; pull_requests: number; issues: number; reviews: number
}
export type RCIDimension = 'code' | 'pr' | 'issue' | 'review'
export type RCIWeights = Record<RCIDimension, number>
export interface RCIRawMetrics {
  effective_commits: number; raw_commits: number; filtered_churn: number; robust_churn: number
  merged_prs: number; effective_issues: number; effective_reviews: number
}
export interface RCIContributor {
  github_username: string; member_id: number | null; user_id: number | null
  display_name: string; is_mapped: boolean; is_bot: boolean; total_events: number
  activity_rank: number; rci: number; rci_rank: number
  dimension_scores: RCIWeights; composition: RCIWeights
  raw_metrics: RCIRawMetrics; weighted_contributions: RCIWeights
}
export interface ContributionIndex {
  repository_id: number; methodology_version: 'RCI_V1'
  mode: 'RESEARCH_BASELINE' | 'CUSTOM_WEIGHTS'
  requested_weights: RCIWeights; effective_weights: RCIWeights
  active_dimensions: RCIDimension[]
  metric_coverage: {
    code_churn_coverage: number; pr_status_coverage: number
    issue_state_reason_coverage: number; review_metadata_coverage: number
  }
  analysis_scope: { description: string; last_sync_at: string | null }
  contributors: RCIContributor[]
}
export interface TimelinePoint extends Omit<Totals, 'events'> { date: string; total: number }
export interface ContributionEvent {
  id: number; event_id: string; event_type: EventType; author_login: string | null
  member_id: number | null; member_display_name: string | null; title: string
  github_url: string | null; event_created_at: string | null; metadata: Record<string, unknown>
}
export interface EventPage { total: number; items: ContributionEvent[] }
export interface SyncResult {
  repository_id: number; repository: string; status: 'SUCCESS' | 'FAILED' | 'RUNNING'
  fetched: number; inserted: number; updated: number; unchanged: number
  mapped: number; unmapped: number; started_at: string; finished_at: string | null
}
export interface SyncRecord {
  id: number; repository_id: number; status: string; started_at: string; finished_at: string | null
  fetched_count: number; inserted_count: number; updated_count: number; unchanged_count: number
  mapped_count: number; unmapped_count: number; error_message: string | null
}
export interface AnalysisResult {
  repository: Repository; created: boolean; sync: SyncResult
  analysis_scope: { max_pages: number; max_prs_for_reviews: number; scope_limited: boolean }
}
export interface Member {
  id: number; repository_id: number; display_name: string; github_username: string
  github_user_id: number | null; user_id: number | null; mapped_event_count: number
}
export interface RepositoryAccess {
  user_id: number; username: string; display_name: string; email: string | null
  is_active: boolean; role: Role; explicit: boolean
}
