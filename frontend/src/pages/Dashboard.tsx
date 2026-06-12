import { useState } from 'react'
import { Grid, Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { KPICard } from '../components/kpi/KPICard'
import { TimeSeriesChart } from '../components/charts/TimeSeriesChart'
import { useKPIs, useTimeSeries, useDevices, useReadiness } from '../hooks/useMetrics'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../components/ui/Select'
import { Loader2 } from 'lucide-react'

const HR_ZONES = [
  { name: 'Zone 1', min: 0, max: 120, color: '#22c55e' },
  { name: 'Zone 2', min: 120, max: 140, color: '#eab308' },
  { name: 'Zone 3', min: 140, max: 160, color: '#f97316' },
  { name: 'Zone 4', min: 160, max: 180, color: '#ef4444' },
  { name: 'Zone 5', min: 180, max: 220, color: '#991b1b' }
]

export function Dashboard() {
  const { data: kpis, isLoading: kpisLoading } = useKPIs()
  const { data: devices, isLoading: devicesLoading } = useDevices()
  const { data: readiness, isLoading: readinessLoading } = useReadiness()
  const [selectedDevice, setSelectedDevice] = useState<string | undefined>()
  const [hrData, setHrData] = useState<any>(null)

  // Fetch time series when device changes
  const hrTimeSeries = useTimeSeries('hr', selectedDevice, '1h')
  const hrvTimeSeries = useTimeSeries('hrv_sdnn', selectedDevice, '1h')

  if (kpisLoading || readinessLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Dashboard</h1>
          <p className="text-surface-500 dark:text-surface-400 mt-1">Health analytics overview for your Helio Ring/Strap</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedDevice} onValueChange={setSelectedDevice}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="All devices" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All devices</SelectItem>
              {devices?.map(d => (
                <SelectItem key={d.device_id} value={d.device_id}>
                  {d.name || d.device_id} ({d.type})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KPICard
          title="Resting HR"
          value={kpis?.resting_hr ?? '—'}
          unit="bpm"
          trend={kpis?.hrv_trend}
          sparklineData={hrTimeSeries.data?.points?.slice(-30).map((p: any) => p.value)}
          sparklineColor="red-500"
          subtitle="During sleep (0-6 AM)"
        />
        <KPICard
          title="HRV (SDNN)"
          value={kpis?.hrv_trend?.current ?? '—'}
          unit="ms"
          trend={kpis?.hrv_trend}
          sparklineData={hrvTimeSeries.data?.points?.slice(-30).map((p: any) => p.value)}
          sparklineColor="brand-500"
          subtitle={`Baseline: ${kpis?.hrv_trend?.baseline ?? '—'} ms`}
        />
        <KPICard
          title="SpO₂ Avg"
          value={kpis?.spo2_avg ?? '—'}
          unit="%"
          sparklineColor="green-500"
          subtitle="Nocturnal average"
        />
        <KPICard
          title="Skin Temp"
          value={kpis?.skin_temp_baseline ?? '—'}
          unit="°C"
          sparklineColor="orange-500"
          subtitle="Circadian baseline"
        />
        <KPICard
          title="Recovery Score"
          value={readiness?.score ?? kpis?.recovery_score ?? '—'}
          unit="/100"
          trend={readiness?.label === 'optimal' ? { direction: 'up', changePct: 0 } :
                 readiness?.label === 'needs_recovery' ? { direction: 'down', changePct: 0 } :
                 { direction: 'stable', changePct: 0 }}
          sparklineColor={readiness?.label === 'optimal' ? 'green-500' :
                          readiness?.label === 'needs_recovery' ? 'red-500' : 'yellow-500'}
          subtitle={readiness?.label}
        />
        <KPICard
          title="Sleep Quality"
          value={kpis?.sleep_quality ?? '—'}
          unit="%"
          sparklineColor="purple-500"
          subtitle="Sleep efficiency"
        />
      </div>

      {/* Readiness Summary */}
      {readiness && (
        <Card variant="hover">
          <CardHeader>
            <CardTitle>Readiness Summary</CardTitle>
            <CardDescription>Weighted: HRV 40% • Sleep 30% • Temperature 15% • Strain 15%</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <ReadinessFactorCard
                label="HRV"
                score={readiness.factors.hrv.score}
                trend={readiness.factors.hrv.trend}
                detail={`Current: ${readiness.factors.hrv.current}ms • Baseline: ${readiness.factors.hrv.baseline}ms`}
                color="brand-500"
              />
              <ReadinessFactorCard
                label="Sleep"
                score={readiness.factors.sleep.score}
                trend="stable"
                detail={`Quality: ${readiness.factors.sleep.quality} • ${readiness.factors.sleep.duration_hours}h`}
                color="purple-500"
              />
              <ReadinessFactorCard
                label="Temperature"
                score={readiness.factors.temperature.score}
                trend={readiness.factors.temperature.deviation > 0 ? 'up' : 'stable'}
                detail={`Deviation: ${readiness.factors.temperature.deviation > 0 ? '+' : ''}${readiness.factors.temperature.deviation.toFixed(1)}°C`}
                color="orange-500"
              />
              <ReadinessFactorCard
                label="Strain"
                score={readiness.factors.strain.score}
                trend="stable"
                detail={`Weekly load: ${readiness.factors.strain.weekly_load}`}
                color="red-500"
              />
            </div>

            <div className="mt-4 p-4 bg-surface-50 dark:bg-surface-800/50 rounded-lg">
              <h4 className="font-medium text-surface-900 dark:text-surface-100 mb-2">Recommendations</h4>
              <ul className="space-y-1 list-disc list-inside text-sm text-surface-600 dark:text-surface-400">
                {readiness.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Heart Rate Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Heart Rate (24h)</CardTitle>
            <CardDescription>Continuous monitoring with zone overlays</CardDescription>
          </CardHeader>
          <CardContent>
            {hrTimeSeries.isLoading ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
              </div>
            ) : hrTimeSeries.data?.points?.length ? (
              <TimeSeriesChart
                data={hrTimeSeries.data.points}
                metric="hr"
                title="Heart Rate"
                yAxisLabel="BPM"
                zones={HR_ZONES}
                height={320}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-surface-500">
                No heart rate data available
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>HRV Trend (7 days)</CardTitle>
            <CardDescription>Daily SDNN with baseline band</CardDescription>
          </CardHeader>
          <CardContent>
            {hrvTimeSeries.isLoading ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
              </div>
            ) : hrvTimeSeries.data?.points?.length ? (
              <TimeSeriesChart
                data={hrvTimeSeries.data.points}
                metric="hrv_sdnn"
                title="HRV (SDNN)"
                yAxisLabel="ms"
                height={320}
              />
            ) : (
              <div className="flex items-center justify-center h-64 text-surface-500">
                No HRV data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ReadinessFactorCard({ label, score, trend, detail, color }: {
  label: string
  score: number
  trend: 'up' | 'down' | 'stable'
  detail: string
  color: string
}) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'
  const trendColor = trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-surface-500'

  return (
    <div className="p-4 bg-white dark:bg-surface-900 rounded-lg border border-surface-200 dark:border-surface-700">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-surface-500 dark:text-surface-400">{label}</span>
        <span className={clsx('text-2xl font-bold', `text-${color}`)}>
          {score}
          <span className={clsx('text-sm font-normal ml-1', trendColor)}>{trendIcon}</span>
        </span>
      </div>
      <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">{detail}</p>
    </div>
  )
}