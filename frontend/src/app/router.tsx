/**
 * Route structure (TRD 7.2).
 *
 * The full navigation tree exists now, so later phases replace a screen rather than
 * restructure routing. Screens whose module is not built render `PlannedPage`, which
 * names the phase and deliberately shows no data.
 */

import { Navigate, createBrowserRouter } from 'react-router-dom'

import { RedirectIfAuthenticated, RequireAuth, RequireRole, RoleHomeRedirect } from './guards'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { PlannedPage } from '@/features/PlannedPage'
import { FarmerHome } from '@/features/farmer/FarmerHome'
import { FieldsPage } from '@/features/farmer/FieldsPage'
import { CheckHealthPage } from '@/features/farmer/CheckHealthPage'
import { MyObservationsPage } from '@/features/farmer/MyObservationsPage'
import { ObservationResultPage } from '@/features/farmer/ObservationResultPage'
import { ExpertHome } from '@/features/expert/ExpertHome'
import { ReviewQueuePage } from '@/features/expert/ReviewQueuePage'
import { ReviewDetailPage } from '@/features/expert/ReviewDetailPage'
import { MapPage } from '@/features/map/MapPage'
import { OfficialHome } from '@/features/official/OfficialHome'
import { OfficialObservationDetailPage } from '@/features/official/OfficialObservationDetailPage'
import { AdminHome } from '@/features/admin/AdminHome'

export const router = createBrowserRouter([
  { path: '/', element: <RoleHomeRedirect /> },
  {
    path: '/login',
    element: (
      <RedirectIfAuthenticated>
        <LoginPage />
      </RedirectIfAuthenticated>
    ),
  },
  {
    path: '/register',
    element: (
      <RedirectIfAuthenticated>
        <RegisterPage />
      </RedirectIfAuthenticated>
    ),
  },

  // ---- FARMER ----
  {
    path: '/app',
    element: (
      <RequireRole roles={['FARMER']}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <FarmerHome /> },
      { path: 'fields', element: <FieldsPage /> },
      // Observation capture depends on the AI pipeline (Phase 2).
      { path: 'check', element: <CheckHealthPage /> },
      { path: 'observations/:id', element: <ObservationResultPage /> },
      { path: 'observations', element: <MyObservationsPage /> },
      // Farmer's own map (own observations only - hotspot detection stays
      // EXTENSION_WORKER/OFFICIAL/ADMIN, per existing RBAC; MapPage hides that
      // toggle for a role without VIEW_HOTSPOTS).
      { path: 'map', element: <MapPage /> },
      { path: 'reports', element: <PlannedPage titleKey="nav.reports" phase="a later phase" /> },
      { path: 'alerts', element: <PlannedPage titleKey="nav.alerts" phase="a later phase" /> },
      // Advisory and follow-up are fully built (Phase 6/7) but live embedded in each
      // observation's own detail page rather than as a separate aggregate list - see
      // `/app/observations/:id`. These redirect there instead of claiming "not
      // implemented" for a feature that exists.
      { path: 'advisory', element: <Navigate to="/app/observations" replace /> },
      { path: 'followups', element: <Navigate to="/app/observations" replace /> },
      { path: 'expert-help', element: <PlannedPage titleKey="nav.expertHelp" phase="a later phase" /> },
    ],
  },

  // ---- EXPERT (extension worker + laboratory) ----
  {
    path: '/expert',
    element: (
      <RequireRole roles={['EXTENSION_WORKER', 'LAB_EXPERT']}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <ExpertHome /> },
      { path: 'queue', element: <ReviewQueuePage /> },
      { path: 'cases/:id', element: <ReviewDetailPage /> },
      // Lab referral is a future extension of the review workflow, not this phase.
      { path: 'referrals', element: <PlannedPage titleKey="nav.cases" phase="Phase 5" /> },
      { path: 'map', element: <MapPage /> },
    ],
  },

  // ---- OFFICIAL ----
  {
    path: '/official',
    element: (
      <RequireRole roles={['OFFICIAL']}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <OfficialHome /> },
      { path: 'observations/:id', element: <OfficialObservationDetailPage /> },
      { path: 'map', element: <MapPage /> },
      { path: 'hotspots', element: <MapPage /> },
      // Priority-zone ranking (beyond raw hotspots) is Phase 8 (official dashboards).
      { path: 'priority-zones', element: <PlannedPage titleKey="nav.hotspots" phase="Phase 8" /> },
      { path: 'trends', element: <PlannedPage titleKey="nav.trends" phase="Phase 8" /> },
    ],
  },

  // ---- ADMIN ----
  {
    path: '/admin',
    element: (
      <RequireRole roles={['ADMIN']}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <AdminHome /> },
      { path: 'users', element: <PlannedPage titleKey="nav.users" phase="Phase 2" /> },
      { path: 'catalog', element: <PlannedPage titleKey="nav.catalog" phase="Phase 2" /> },
      { path: 'data-sources', element: <PlannedPage titleKey="nav.dataSources" phase="Phase 4" /> },
      { path: 'audit', element: <PlannedPage titleKey="nav.audit" phase="Phase 2" /> },
    ],
  },

  {
    path: '*',
    element: (
      <RequireAuth>
        <RoleHomeRedirect />
      </RequireAuth>
    ),
  },
])
