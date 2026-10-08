import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // A 401 from /auth/* just means "wrong credentials": let the form show it.
    // Anywhere else it means the session expired, so go back to sign-in.
    const isAuthCall = err.config?.url?.startsWith('/auth/')
    if (err.response?.status === 401 && !isAuthCall) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// Files (previews, 3D models) need a login, but <img> and the 3D viewer cannot send
// an Authorization header. So we fetch a short-lived link token and put it in the URL.
let tokenCache = { value: null, expires: 0 }

export async function fileUrl(projectId, name) {
  if (!tokenCache.value || Date.now() > tokenCache.expires) {
    const { data } = await api.post('/files/token')
    tokenCache = { value: data.token, expires: Date.now() + (data.expires_in - 120) * 1000 }
  }
  return `${API_URL}/files/${projectId}/${name}?t=${encodeURIComponent(tokenCache.value)}`
}

/** Normalize any axios/FastAPI error (including 422 `detail` arrays) to a string. */
export function apiErrorMessage(err, fallback = 'Something went wrong') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d?.msg).filter(Boolean)
    if (msgs.length) return msgs.join('; ')
  }
  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail)
    } catch {
      /* fall through */
    }
  }
  return err?.message || fallback
}

export default api