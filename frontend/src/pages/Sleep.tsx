import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Loader2 } from 'lucide-react'

export function Sleep() {
  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Sleep</h1>
        <p className="text-surface-500 dark:text-surface-400 mt-1">Sleep staging, hypnogram, and quality metrics</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Sleep Analysis</CardTitle>
          <CardDescription>Hypnogram, phase durations, efficiency, consistency</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-96">
          <div className="text-center text-surface-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-brand-500" />
            <p>Sleep analysis coming soon</p>
            <p className="text-sm mt-1">Connect your Helio device to see sleep data</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}