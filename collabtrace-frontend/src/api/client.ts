import axios, { AxiosError } from 'axios'

export const TOKEN_KEY = 'collabtrace_access_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 180_000,
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(undefined, (error: AxiosError) => {
  if (error.response?.status === 401 && sessionStorage.getItem(TOKEN_KEY)) {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.setItem('collabtrace_auth_notice', '登录状态已失效，请重新登录。')
    window.dispatchEvent(new Event('collabtrace:unauthorized'))
  }
  return Promise.reject(error)
})

export function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return '发生未知错误，请重试。'
  const detail = error.response?.data && typeof error.response.data === 'object'
    ? (error.response.data as { detail?: string }).detail : undefined
  if (detail) return detail
  if (!error.response) return '无法连接服务器，请确认 Backend 已启动。'
  if (error.response.status === 403) return 'You do not have permission to perform this action.'
  if (error.response.status === 404) return '请求的数据不存在。'
  if (error.response.status === 429) return '请求过于频繁，请稍后再试。'
  return '请求失败，请稍后重试。'
}
