import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { clsx } from 'clsx'

interface MiniAreaChartProps {
  data: number[]
  color?: string
  height?: number
  width?: number
  className?: string
  strokeWidth?: number
}

export function MiniAreaChart({ data, color = 'brand-500', height = 48, width, className, strokeWidth = 2 }: MiniAreaChartProps) {
  if (!data || data.length === 0) {
    return <div className={clsx('h-full', className)} />
  }

  // Convert to array of objects for recharts
  const chartData = data.map((value, index) => ({ value, index }))

  const colorMap: Record<string, string> = {
    'brand-500': '#0ea5e9',
    'green-500': '#22c55e',
    'red-500': '#ef4444',
    'yellow-500': '#eab308',
    'purple-500': '#a855f7',
    'orange-500': '#f97316',
    'teal-500': '#14b8a6'
  }

  const strokeColor = colorMap[color] || color
  const fillColor = strokeColor.replace(')', ', 0.1)').replace('rgb', 'rgba').replace('#', '')

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0} vertical={false} horizontal={false} />
        <XAxis type="number" dataKey="index" axisLine={false} tickLine={false} tick={false} />
        <YAxis type="number" domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={false} />
        <Tooltip
          content={({ active, payload }) => {
            if (active && payload && payload.length) {
              return (
                <div className="bg-surface-900 text-surface-100 px-2 py-1 rounded text-xs">
                  {payload[0].value.toFixed(1)}
                </div>
              )
            }
            return null
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          dot={false}
          activeDot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="none"
          fillOpacity={0.1}
          fill={strokeColor}
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  )
}