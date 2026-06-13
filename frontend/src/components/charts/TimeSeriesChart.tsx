import { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Brush, ReferenceArea, Legend
} from 'recharts'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card'
import { Button } from '../ui/Button'
import { clsx } from 'clsx'
import { format } from 'date-fns'

interface TimeSeriesPoint {
  timestamp_ms: number
  value: number
  min?: number
  max?: number
  avg?: number
}

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[]
  metric: string
  title: string
  description?: string
  yAxisLabel?: string
  zones?: Array<{ name: string; min: number; max: number; color: string }>
  height?: number
  showBrush?: boolean
  onBrushChange?: (range: [number, number]) => void
  className?: string
}

const METRIC_COLORS: Record<string, string> = {
  hr: '#ef4444',
  hrv_sdnn: '#0ea5e9',
  hrv_rmssd: '#06b6d4',
  spo2: '#22c55e',
  skin_temp: '#f97316',
  eda: '#a855f7'
}

export function TimeSeriesChart({
  data,
  metric,
  title,
  description,
  yAxisLabel,
  zones,
  height = 400,
  showBrush = true,
  onBrushChange,
  className
}: TimeSeriesChartProps) {
  const [brushRange, setBrushRange] = useState<[number, number] | null>(null)
  const color = METRIC_COLORS[metric] || '#0ea5e9'

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return []
    return data.map((d, i) => ({
      ...d,
      timestamp: new Date(d.timestamp_ms),
      index: i,
      formattedTime: format(new Date(d.timestamp_ms), 'MMM d HH:mm')
    }))
  }, [data])

  const yDomain = useMemo(() => {
    if (!chartData.length) return [0, 100] as const
    const values = chartData.flatMap(d => [d.value, d.min, d.max].filter(v => v !== undefined))
    const min = Math.min(...values)
    const max = Math.max(...values)
    const padding = (max - min) * 0.1
    return [Math.max(0, min - padding), max + padding] as const
  }, [chartData])

  const handleBrushChange = (range: { startIndex: number; endIndex: number }) => {
    const newRange: [number, number] = [range.startIndex, range.endIndex]
    setBrushRange(newRange)
    onBrushChange?.(newRange)
  }

  if (!chartData.length) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent className="flex items-center justify-center h-64">
          <div className="text-center text-surface-500">
            <p>No data available</p>
            <p className="text-sm mt-1">Select a different date range or check device connection</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          <div className="flex items-center gap-2">
            {brushRange && (
              <Button variant="ghost" size="sm" onClick={() => { setBrushRange(null); onBrushChange?.([0, chartData.length - 1]); }}>
                Reset zoom
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ height: height + 'px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                type="number"
                dataKey="index"
                tickFormatter={(value) => chartData[value]?.formattedTime || ''}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
                dy={10}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={yDomain}
                label={{ value: yAxisLabel || metric.toUpperCase(), angle: -90, position: 'insideLeft', offset: -10, fill: '#64748b', fontSize: 11 }}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
                width={50}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload || !payload.length) return null
                  const point = chartData[Number(label)]
                  return (
                    <div className="bg-surface-900 text-surface-100 px-3 py-2 rounded-lg shadow-lg border border-surface-700">
                      <p className="font-medium mb-1">{point?.formattedTime}</p>
                      {payload.map((entry, i) => (
                        <p key={i} className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                          <span>{entry.name}: <strong>{entry.value.toFixed(1)}</strong></span>
                        </p>
                      ))}
                    </div>
                  )
                }}
              />
              <Legend
                layout="horizontal"
                align="center"
                verticalAlign="bottom"
                iconType="line"
                iconHeight={8}
                bottom={-30}
              />

              {/* HR Zones as reference areas */}
              {zones && zones.map((zone, i) => (
                <ReferenceArea
                  key={zone.name}
                  y1={zone.min}
                  y2={zone.max}
                  fill={zone.color}
                  fillOpacity={0.08}
                  stroke={zone.color}
                  strokeOpacity={0.3}
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
              ))}

              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6, strokeWidth: 2 }}
                connectNulls
                name={metric.toUpperCase()}
              />

              {showBrush && (
                <Brush
                  dataKey="index"
                  height={30}
                  startIndex={brushRange?.[0] ?? 0}
                  endIndex={brushRange?.[1] ?? chartData.length - 1}
                  onChange={handleBrushChange}
                  tickFormatter={(value) => chartData[value]?.formattedTime || ''}
                >
                  <rect fill="#0ea5e9" fillOpacity={0.1} />
                </Brush>
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}