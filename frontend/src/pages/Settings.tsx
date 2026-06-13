import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Loader2 } from 'lucide-react'

export function Settings() {
  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Settings</h1>
        <p className="text-surface-500 dark:text-surface-400 mt-1">Device, calendar, privacy, and backup settings</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Device Management</CardTitle>
          <CardDescription>Pair and manage Helio Ring/Strap devices</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <div>
              <p className="font-medium text-surface-900 dark:text-surface-100">Helio Ring</p>
              <p className="text-sm text-surface-500 dark:text-surface-400">Not connected</p>
            </div>
            <Button variant="primary" disabled>Connect</Button>
          </div>
          <div className="flex items-center justify-between p-4 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <div>
              <p className="font-medium text-surface-900 dark:text-surface-100">Helio Strap</p>
              <p className="text-sm text-surface-500 dark:text-surface-400">Not connected</p>
            </div>
            <Button variant="primary" disabled>Connect</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Calendar Integration</CardTitle>
          <CardDescription>Connect Google Calendar, Outlook, or iOS Calendar</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="primary" onClick={() => window.location.href = '/settings/calendar'}>
            Manage Calendars
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Privacy & Data</CardTitle>
          <CardDescription>Control data retention, encryption, and exports</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <div>
              <p className="font-medium text-surface-900 dark:text-surface-100">Encryption</p>
              <p className="text-sm text-surface-500 dark:text-surface-400">Encrypt local database at rest</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-surface-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 dark:peer-focus:ring-brand-900 rounded-full peer dark:bg-surface-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-surface-600 peer-checked:bg-brand-500"></div>
            </label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data Export</CardTitle>
          <CardDescription>Export your health data and stress correlations</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="secondary" className="w-full" onClick={() => window.open('/api/v1/export/?format=csv', '_blank')}>
            Export All Data (CSV)
          </Button>
          <Button variant="secondary" className="w-full" onClick={() => window.open('/api/v1/export/correlation?format=csv', '_blank')}>
            Export Stress Correlation (CSV)
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}