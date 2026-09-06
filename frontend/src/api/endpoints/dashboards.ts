/** Official dashboard binding (Phase 8). One aggregated read - see the backend's
 * `DashboardService`, which computes nothing new: every figure is a straight read of
 * data the observation/AI/risk/GIS/review/follow-up modules already produced. */
import { apiGet } from '@/api/client'

export interface DashboardOverview {
  total_observations: number
  high_risk_observations: number
  pending_expert_reviews: number
  confirmed_cases: number
  active_hotspots: number
  followups_requiring_attention: number
}

export interface TopThreat {
  agent_id: string
  agent_code: string | null
  agent_name: string | null
  kind: string | null
  total_observations: number
  confirmed_observations: number
}

export interface AffectedCrop {
  crop_id: string
  crop_code: string | null
  crop_name: string | null
  total_observations: number
}

export interface DiseasePestSummary {
  top_threats: TopThreat[]
  affected_crops: AffectedCrop[]
  risk_distribution: { LOW: number; MEDIUM: number; HIGH: number }
  diagnosis_basis: { confirmed: number; ai_predicted_only: number }
}

export interface PriorityArea {
  cluster_id: number
  label: string
  hotspot_type: 'CONFIRMED' | 'SIGNAL' | 'PREDICTED'
  centroid: { latitude: number; longitude: number }
  observation_count: number
  confirmed_count: number
  dominant_agent_code: string | null
  dominant_agent_name: string | null
  avg_severity: number | null
  includes_demo_data: boolean
  disclaimer_key: string
}

export interface DashboardActivityObservation {
  id: string
  observed_at: string
  verification_status: string
  source_type: string
  crop_id: string | null
}

export interface DashboardActivityFollowup {
  id: string
  parent_observation_id: string
  outcome: string | null
  status: string
  submitted_at: string | null
  notes: string | null
}

export interface RecentActivity {
  observations: DashboardActivityObservation[]
  expert_validations: DashboardActivityObservation[]
  high_risk_cases: DashboardActivityObservation[]
  worsening_followups: DashboardActivityFollowup[]
}

export interface OfficialDashboard {
  overview: DashboardOverview
  disease_pest_summary: DiseasePestSummary
  priority_areas: PriorityArea[]
  recent_activity: RecentActivity
  includes_demo_data: boolean
  disclaimer_key: string
}

export const dashboardsApi = {
  official: (includeDemo = false) =>
    apiGet<OfficialDashboard>('/dashboards/official', { params: { include_demo: includeDemo } }),
}
