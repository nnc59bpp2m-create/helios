import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Loader2 } from 'lucide-react'

export function StressLeaderboard() {
  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Stress Leaderboard</h1>
        <p className="text-surface-500 dark:text-surface-400 mt-1">Ranked meetings and colleagues by stress impact</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Stress Leaderboard</CardTitle>
          <CardDescription>People, series, time-slots, and categories ranked</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-96">
          <div className="text-center text-surface-500">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-brand-500" />
            <p>Leaderboard coming soon</p>
            <p className="text-sm mt-1">Connect calendar to rank stress by person/meeting</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}