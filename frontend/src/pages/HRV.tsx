import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Loader2 } from 'lucide-react'

export function HRV() {
  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">HRV</h1>
        <p className="text-surface-500 dark:text-surface-400 mt-1">Heart Rate Variability trends and readiness correlation</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>HRV (SDNN/RMSSD)</CardTitle>
          <CardDescription>Daily trends with baseline band</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-96">
          <div className="text-center text-surface-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-brand-500" />
            <p>HRV chart coming soon</p>
            <p className="text-sm mt-1">Connect your Helio device to see live data</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}