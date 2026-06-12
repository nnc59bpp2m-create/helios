import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

interface DateRange {
  from: Date | undefined
  to: Date | undefined
}

interface GlobalFilterContextType {
  dateRange: DateRange
  setDateRange: (range: DateRange) => void
  deviceId: string | undefined
  setDeviceId: (id: string | undefined) => void
  preset: string
  setPreset: (preset: string) => void
}

const GlobalFilterContext = createContext<GlobalFilterContextType | undefined>(undefined)

const PRESETS = {
  '7d': { days: 7, label: 'Last 7 days' },
  '30d': { days: 30, label: 'Last 30 days' },
  '90d': { days: 90, label: 'Last 90 days' },
  '1y': { days: 365, label: 'Last year' }
}

export function GlobalFilterProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [dateRange, setDateRangeState] = useState<DateRange>(() => {
    const fromParam = searchParams.get('from')
    const toParam = searchParams.get('to')
    return {
      from: fromParam ? new Date(fromParam) : undefined,
      to: toParam ? new Date(toParam) : undefined
    }
  })
  const [deviceId, setDeviceIdState] = useState<string | undefined>(() => searchParams.get('device') || undefined)
  const [preset, setPresetState] = useState<string>(() => searchParams.get('preset') || '30d')

  // Sync to URL
  useEffect(() => {
    const params = new URLSearchParams()
    if (dateRange.from) params.set('from', dateRange.from.toISOString())
    if (dateRange.to) params.set('to', dateRange.to.toISOString())
    if (deviceId) params.set('device', deviceId)
    if (preset && preset !== '30d') params.set('preset', preset)
    setSearchParams(params, { replace: true })
  }, [dateRange, deviceId, preset, setSearchParams])

  // Apply preset
  useEffect(() => {
    if (preset && PRESETS[preset as keyof typeof PRESETS]) {
      const days = PRESETS[preset as keyof typeof PRESETS].days
      const to = new Date()
      const from = new Date()
      from.setDate(to.getDate() - days)
      setDateRangeState({ from, to })
    }
  }, [preset])

  const setDateRange = (range: DateRange) => {
    setDateRangeState(range)
    setPresetState('custom')
  }

  const setDeviceId = (id: string | undefined) => {
    setDeviceIdState(id)
  }

  const setPreset = (p: string) => {
    setPresetState(p)
  }

  return (
    <GlobalFilterContext.Provider value={{ dateRange, setDateRange, deviceId, setDeviceId, preset, setPreset }}>
      {children}
    </GlobalFilterContext.Provider>
  )
}

export function useGlobalFilter() {
  const context = useContext(GlobalFilterContext)
  if (!context) {
    throw new Error('useGlobalFilter must be used within a GlobalFilterProvider')
  }
  return context
}