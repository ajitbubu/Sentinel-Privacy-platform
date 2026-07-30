import axios, { AxiosInstance } from 'axios'

/** Shared HTTP client with auth injection and retry-on-429. */
export function createApiClient(baseURL: string, getToken: () => string | null): AxiosInstance {
  const client = axios.create({ baseURL })
  client.interceptors.request.use((config) => {
    const token = getToken()
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })
  client.interceptors.response.use(undefined, async (error) => {
    if (error.response?.status === 429) {
      const retryAfter = Number(error.response.headers['retry-after'] ?? 1)
      await new Promise((r) => setTimeout(r, retryAfter * 1000))
      return client.request(error.config)
    }
    throw error
  })
  return client
}
