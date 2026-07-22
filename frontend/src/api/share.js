// 나누다 · 동네 자원 지도 (돌봄일지·가족편지는 api/family.js 로 이동)
import { mockResolve } from './client.js'
import { resources } from '../mock/db.js'

export function listResources() {
  return mockResolve(resources, 700)
}
