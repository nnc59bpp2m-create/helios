import { Card, CardContent } from '../ui/Card'
import { MiniAreaChart } from '../charts/MiniAreaChart'
import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface KPICardProps {
  title: string
  value: string | number | null
  unit?: string
  trend?: { direction: 'up' | 'down' | 'stable'; changePct: number }
  sparklineData?: number[]
  sparklineColor?: string
  subtitle?: string
  className?: string
}

export function KPICard({ title, value, unit, trend, sparklineData, sparklineColor = 'brand-500', subtitle, className }: KPICardProps) {
  const trendIcon = trend?.direction === 'up' ? <TrendingUp className="w-4 h-4 text-green-500" /> :
                    trend?.direction === 'down' ? <TrendingDown className="w-4 h-4 text-red-500" /> :
                    <Minus className="w-4 h-4 text-surface-400" />

  const trendColor = trend?.direction === 'up' ? 'text-green-600 dark:text-green-400' :
                     trend?.direction === 'down' ? 'text-red-600 dark:text-red-400' :
                     'text-surface-500'

  return (
    <Card variant="hover" className={clsx(className)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-surface-500 dark:text-surface-400">{title}</p>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-bold text-surface-900 dark:text-surface-100">
                {value !== null && value !== undefined ? value : '—'}
              </span>
              {unit && <span className="text-sm text-surface-500 dark:text-surface-400 mt-1">{unit}</span>}
            </div>
            {sparklineData && sparklineData.length > 0 && (
              <div className="mt-2 h-12 w-full">
                <MiniAreaChart data={sparklineData} color={sparklineColor} height={48} />
              </div>
            )}
            {subtitle && <p className="text-xs text-surface-500 dark:text-surface-400 mt-2">{subtitle}</p>}
          </div>
          {trend && (
            <div className={clsx('flex items-center gap-1 text-sm font-medium', trendColor)}>
              {trendIcon}
              <span>{trend.changePct >= 0 ? '+' : ''}{trend.changePct.toFixed(1)}%</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}