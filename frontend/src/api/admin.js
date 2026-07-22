// 관리자 · 대시보드/회원/추천이력
import { mockResolve } from './client.js'
import {
  dashboardKpis, aiTrend, featureUsage, adminUsers, adminAccounts,
} from '../mock/db.js'

export function getDashboard() {
  return mockResolve(() => ({ kpis: dashboardKpis, aiTrend, featureUsage }), 600)
}
export function listAdminUsers() { return mockResolve(adminUsers, 500) }
export function listAdminAccounts() { return mockResolve(adminAccounts, 500) }
