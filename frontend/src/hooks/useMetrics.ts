import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useGlobalFilter } from '../context/GlobalFilterContext'

const API_BASE = '/api/v1'

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

// Helper to build query params from global filter
function buildParams(baseUrl: string, extraParams?: Record<string, string>) {
  const params = new URLSearchParams()
  // Global filter params would be added here via context
  if (extraParams) {
    Object.entries(extraParams).forEach(([k, v]) => params.set(k, v))
  }
  return `${baseUrl}?${params.toString()}`
}

// Metrics hooks
export function useKPIs(deviceId?: string) {
  const { dateRange } = useGlobalFilter()
  return useQuery({
    queryKey: ['kpis', deviceId, dateRange.from?.toISOString(), dateRange.to?.toISOString()],
    queryFn: () => fetchJson<{
      resting_hr: number | null
      hrv_trend: any
      spo2_avg: number | null
      skin_temp_baseline: number | null
      recovery_score: number | null
      sleep_quality: number | null
    }>(`${API_BASE}/metrics/kpi` + new URLSearchParams({
      ...(deviceId && { device_id: deviceId }),
      ...(dateRange.from && { days: Math.ceil((dateRange.to?.getTime() || Date.now() - dateRange.from.getTime()) / 86400000).toString() })
    }))
  })
}

export function useTimeSeries(metric: string, deviceId?: string, interval = '1h') {
  const { dateRange } = useGlobalFilter()
  return useQuery({
    queryKey: ['timeseries', metric, deviceId, interval, dateRange.from?.toISOString(), dateRange.to?.toISOString()],
    queryFn: () => fetchJson<{
      metric: string
      interval: string
      points: Array<{ timestamp_ms: number; value: number; min?: number; max?: number; avg?: number }>
    }>(`${API_BASE}/metrics/timeseries` + new URLSearchParams({
      metric,
      interval,
      ...(deviceId && { device_id: deviceId }),
      ...(dateRange.from && { days: Math.ceil((dateRange.to?.getTime() || Date.now() - dateRange.from.getTime()) / 86400000).toString() })
    })),
    enabled: !!metric
  })
}

export function useCorrelation(x: string, y: string, deviceId?: string) {
  const { dateRange } = useGlobalFilter()
  return useQuery({
    queryKey: ['correlation', x, y, deviceId, dateRange.from?.toISOString(), dateRange.to?.toISOString()],
    queryFn: () => fetchJson<{
      x_metric: string
      y_metric: string
      points: Array<{ x: number; y: number }>
      regression: { slope: number; intercept: number } | null
      correlation_coefficient: number | null
    }>(`${API_BASE}/metrics/correlation` + new URLSearchParams({
      x, y,
      ...(deviceId && { device_id: deviceId }),
      ...(dateRange.from && { days: Math.ceil((dateRange.to?.getTime() || Date.now() - dateRange.from.getTime()) / 86400000).toString() })
    })),
    enabled: !!x && !!y
  })
}

export function useDevices() {
  return useQuery({
    queryKey: ['devices'],
    queryFn: () => fetchJson<Array<{ device_id: string; name: string; type: string; active: boolean }>>(`${API_BASE}/metrics/devices`)
  })
}

// Sleep hooks
export function useSleepStages(date: string, deviceId?: string) {
  return useQuery({
    queryKey: ['sleep', 'stages', date, deviceId],
    queryFn: () => fetchJson<any>(`${API_BASE}/sleep/stages` + new URLSearchParams({ date, ...(deviceId && { device_id: deviceId }) })),
    enabled: !!date
  })
}

// Activity hooks
export function useActivitySessions(days = 30, deviceId?: string) {
  return useQuery({
    queryKey: ['activity', 'sessions', days, deviceId],
    queryFn: () => fetchJson<any>(`${API_BASE}/activity/sessions` + new URLSearchParams({ days: days.toString(), ...(deviceId && { device_id: deviceId }) }))
  })
}

// Coach hooks
export function useReadiness(deviceId?: string) {
  return useQuery({
    queryKey: ['coach', 'readiness', deviceId],
    queryFn: () => fetchJson<any>(`${API_BASE}/coach/readiness` + new URLSearchParams({ ...(deviceId && { device_id: deviceId }) }))
  })
}

export function useInsights(days = 7, deviceId?: string) {
  return useQuery({
    queryKey: ['coach', 'insights', days, deviceId],
    queryFn: () => fetchJson<any>(`${API_BASE}/coach/insights` + new URLSearchParams({ days: days.toString(), ...(deviceId && { device_id: deviceId }) }))
  })
}

export function useProjections(days = 30, deviceId?: string) {
  return useQuery({
    queryKey: ['coach', 'projections', days, deviceId],
    queryFn: () => fetchJson<any>(`${API_BASE}/coach/projections` + new URLSearchParams({ days: days.toString(), ...(deviceId && { device_id: deviceId }) }))
  })
}

// Chat hook
export function useCoachChat() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (message: string) => {
      const response = await fetch(`${API_BASE}/coach/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      })
      if (!response.ok) throw new Error('Chat failed')
      return response.json()
    }
  })
}

// Calendar hooks
export function useCalendarAccounts() {
  return useQuery({
    queryKey: ['calendar', 'accounts'],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/calendar/accounts`)
  })
}

export function useCalendarEvents(accountId?: number, days = 30) {
  const { dateRange } = useGlobalFilter()
  return useQuery({
    queryKey: ['calendar', 'events', accountId, days, dateRange.from?.toISOString()],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/calendar/events` + new URLSearchParams({
      ...(accountId && { account_id: accountId.toString() }),
      days: days.toString(),
      ...(dateRange.from && { from: dateRange.from.toISOString() }),
      ...(dateRange.to && { to: dateRange.to.toISOString() })
    }))
  })
}

export function useSyncCalendar(accountId: number) {
  return useMutation({
    mutationFn: () => fetchJson<any>(`${API_BASE}/calendar/accounts/${accountId}/sync`, { method: 'POST' })
  })
}

// Correlation hooks
export function useCorrelatedEvents(days = 30, minScore?: number, maxScore?: number) {
  const { dateRange } = useGlobalFilter()
  return useQuery({
    queryKey: ['correlation', 'events', days, minScore, maxScore, dateRange.from?.toISOString()],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/correlation/events` + new URLSearchParams({
      days: days.toString(),
      ...(minScore !== undefined && { min_score: minScore.toString() }),
      ...(maxScore !== undefined && { max_score: maxScore.toString() }),
      ...(dateRange.from && { from: dateRange.from.toISOString() }),
      ...(dateRange.to && { to: dateRange.to.toISOString() })
    }))
  })
}

export function useEventCorrelation(eventUid: string) {
  return useQuery({
    queryKey: ['correlation', 'event', eventUid],
    queryFn: () => fetchJson<any>(`${API_BASE}/correlation/event/${encodeURIComponent(eventUid)}`),
    enabled: !!eventUid
  })
}

// Leaderboard hooks
export function useLeaderboard(days = 30) {
  return useQuery({
    queryKey: ['leaderboard', days],
    queryFn: () => fetchJson<any>(`${API_BASE}/leaderboard` + new URLSearchParams({ days: days.toString() }))
  })
}

export function usePeopleLeaderboard(days = 30, minEvents = 3) {
  return useQuery({
    queryKey: ['leaderboard', 'people', days, minEvents],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/leaderboard/people` + new URLSearchParams({ days: days.toString(), min_events: minEvents.toString() }))
  })
}

export function useSeriesLeaderboard(days = 30, minEvents = 2) {
  return useQuery({
    queryKey: ['leaderboard', 'series', days, minEvents],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/leaderboard/series` + new URLSearchParams({ days: days.toString(), min_events: minEvents.toString() }))
  })
}

export function useTimeSlotLeaderboard(days = 30) {
  return useQuery({
    queryKey: ['leaderboard', 'time-slots', days],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/leaderboard/time-slots` + new URLSearchParams({ days: days.toString() }))
  })
}

export function useCategoryLeaderboard(days = 30) {
  return useQuery({
    queryKey: ['leaderboard', 'categories', days],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/leaderboard/categories` + new URLSearchParams({ days: days.toString() }))
  })
}

// Sync hooks
export function useSyncStatus() {
  return useQuery({
    queryKey: ['sync', 'status'],
    queryFn: () => fetchJson<any[]>(`${API_BASE}/sync/status`),
    refetchInterval: 30000
  })
}

// Export hooks
export function useExportData(params: any) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (exportParams: any) => {
      const url = `${API_BASE}/export/` + new URLSearchParams(exportParams).toString()
      const response = await fetch(url)
      if (!response.ok) throw new Error('Export failed')
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition')
      const filename = disposition?.match(/filename="(.+)"/)?.[1] || 'export.csv'
      return { blob, filename }
    },
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  })
}