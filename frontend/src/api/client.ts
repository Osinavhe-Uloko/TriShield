import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const api = axios.create({ baseURL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('trishield_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface PredictResponse {
  scan_id: string
  verdict: 'phishing' | 'legitimate'
  confidence: number
  risk_score: number
  reasons: string[]
  feature_breakdown: Record<string, number>
  channel_breakdown?: Record<string, unknown>
  model_version: string
  latency_ms: number
}

export interface ScanHistoryItem {
  id: string
  input_type: string
  input_raw: string
  verdict: string
  confidence: number
  risk_score: number
  model_version: string
  created_at: string
}

export interface AnalyticsSummary {
  total_scans: number
  phishing_count: number
  legitimate_count: number
  by_channel: Record<string, number>
  average_confidence: number
  feedback_accuracy: number | null
  scans_last_7_days: Record<string, number>
}

export async function predictUrl(url: string): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>('/predict/url', { url })
  return data
}

export async function predictEmail(rawEmail: string): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>('/predict/email', { raw_email: rawEmail })
  return data
}

export async function predictWebpage(url: string): Promise<PredictResponse> {
  const { data } = await api.post<PredictResponse>('/predict/webpage', { url })
  return data
}

export async function submitFeedback(scanId: string, userVerdict: 'phishing' | 'legitimate') {
  const { data } = await api.post('/feedback', { scan_id: scanId, user_verdict: userVerdict })
  return data
}

export async function getHistory(limit = 50): Promise<ScanHistoryItem[]> {
  const { data } = await api.get<ScanHistoryItem[]>('/history', { params: { limit } })
  return data
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  const { data } = await api.get<AnalyticsSummary>('/analytics/summary')
  return data
}

export async function login(email: string, password: string): Promise<string> {
  const { data } = await api.post<{ access_token: string }>('/auth/login', { email, password })
  localStorage.setItem('trishield_token', data.access_token)
  return data.access_token
}

export async function register(email: string, password: string): Promise<string> {
  const { data } = await api.post<{ access_token: string }>('/auth/register', { email, password })
  localStorage.setItem('trishield_token', data.access_token)
  return data.access_token
}

export function logout() {
  localStorage.removeItem('trishield_token')
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('trishield_token')
}
