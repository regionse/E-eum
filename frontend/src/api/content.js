// 공지사항 · 문의
import { mockResolve, delay } from './client.js'
import { notices, inquiries } from '../mock/db.js'

// 공지
export function listNotices({ type = '전체', q = '' } = {}) {
  return mockResolve(() => notices.filter((n) =>
    (type === '전체' || n.type === type) && (n.title.includes(q) || n.body.includes(q))
  ), 500)
}
export function getNotice(id) {
  return mockResolve(() => notices.find((n) => String(n.id) === String(id)), 400)
}

// 문의
export function listInquiries() {
  return mockResolve(inquiries, 500)
}
export function getInquiry(id) {
  return mockResolve(() => inquiries.find((i) => String(i.id) === String(id)), 400)
}
export async function submitInquiry(data) {
  await delay(700)
  inquiries.unshift({ id: Date.now(), status: '접수', answer: '', date: '2026-07-07', ...data })
  return { ok: true }
}
