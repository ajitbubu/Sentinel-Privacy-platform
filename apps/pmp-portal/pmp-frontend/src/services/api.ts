import axios from 'axios'

export const api = axios.create({ baseURL: '/api/v1' })

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try one silent refresh, then retry the original request.
let refreshing: Promise<boolean> | null = null

api.interceptors.response.use(undefined, async (error) => {
  const original = error.config
  const isAuthCall = original?.url?.startsWith('/auth/')
  if (error.response?.status === 401 && !original._retried && !isAuthCall) {
    original._retried = true
    const { refreshSession } = await import('./auth')
    refreshing = refreshing ?? refreshSession()
    const ok = await refreshing
    refreshing = null
    if (ok) return api.request(original)
    window.location.href = '/login'
  }
  throw error
})
