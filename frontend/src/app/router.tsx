/**
 * Route structure (TRD 7.2).
 *
 * The full navigation tree exists now, so later phases replace a screen rather than
 * restructure routing. Screens whose module is not built render `PlannedPage`, which
 * names the phase and deliberately shows no data.
 */

import { createBrowserRouter } from 'react-router-dom'

import { RedirectIfAuthenticated, RequireAuth, RequireRole, RoleHomeRedirect } from './guards'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/features/auth/LoginPage'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { PlannedPage } from '@/features/PlannedPage'
import { FarmerHome } from '@/features/farmer/FarmerHome'
import { FieldsPage } from '@/features/farmer/FieldsPage'
import { ExpertHome } from '@/features/expert/ExpertHome'
import { OfficialHome } from '@/features/official/OfficialHome'
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
      { path: 'check', element: <PlannedPage titleKey="nav.checkHealth" phase="Phase 2" /> },
      { path: 'reports', element: <PlannedPage titleKey="nav.reports" phase="Phase 2" /> },
      { path: 'alerts', element: <PlannedPage titleKey="nav.alerts" phase="Phase 8" /> },
      { path: 'advisory', element: <PlannedPage titleKey="nav.advisory" phase="Phase 6" /> },
      { path: 'followups', element: <PlannedPage titleKey="nav.reports" phase="Phase 7" /> },
      { path: 'expert-help', element: <PlannedPage titleKey="nav.expertHelp" phase="Phase 5" /> },
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
      { path: 'queue', element: <PlannedPage titleKey="nav.queue" phase="Phase 5" /> },
      { path: 'cases/:id', element: <PlannedPage titleKey="nav.cases" phase="Phase 5" /> },
      { path: 'referrals', element: <PlannedPage titleKey="nav.cases" phase="Phase 5" /> },
      { path: 'map', element: <PlannedPage titleKey="nav.map" phase="Phase 4" /> },
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
      { path: 'map', element: <PlannedPage titleKey="nav.map" phase="Phase 4" /> },
      { path: 'hotspots', element: <PlannedPage titleKey="nav.hotspots" phase="Phase 4" /> },
      { path: 'priority-zones', element: <PlannedPage titleKey="nav.hotspots" phase="Phase 4" /> },
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
