// 관리자 · 회원/추천이력
import { mockResolve } from './client.js'
import {
  adminUsers, adminAccounts,
} from '../mock/db.js'

export function listAdminUsers() { return mockResolve(adminUsers, 500) }
export function listAdminAccounts() { return mockResolve(adminAccounts, 500) }
