import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Loader2 } from 'lucide-react'
import { useState } from 'react'

export function CalendarSettings() {
  const [googleConnected, setGoogleConnected] = useState(false)
  const [outlookConnected, setOutlookConnected] = useState(false)
  const [iosConnected, setIosConnected] = useState(false)

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">Calendar Settings</h1>
          <p className="text-surface-500 dark:text-surface-400 mt-1">Connect and manage calendar sources for stress correlation</p>
        </div>
      </div>

      {/* Google Calendar */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Google Calendar</CardTitle>
              <CardDescription>OAuth 2.0 with incremental sync</CardDescription>
            </div>
            {googleConnected ? (
              <Button variant="secondary" onClick={() => setGoogleConnected(false)}>Disconnect</Button>
            ) : (
              <Button variant="primary" onClick={() => setGoogleConnected(true)}>Connect</Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {googleConnected && (
            <div className="space-y-2 text-sm">
              <p className="text-green-600 dark:text-green-400">✓ Connected</p>
              <p className="text-surface-500">Syncing every 15 minutes</p>
              <p className="text-surface-500">Categories: 1:1, team, all-hands, external, focus</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Microsoft Outlook / Graph */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Microsoft Outlook / Graph</CardTitle>
              <CardDescription>OAuth 2.0 with device code flow for MDM/Intune</CardDescription>
            </div>
            {outlookConnected ? (
              <Button variant="secondary" onClick={() => setOutlookConnected(false)}>Disconnect</Button>
            ) : (
              <Button variant="primary" onClick={() => setOutlookConnected(true)}>Connect</Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {outlookConnected && (
            <div className="space-y-2 text-sm">
              <p className="text-green-600 dark:text-green-400">✓ Connected</p>
              <p className="text-surface-500">Device code flow enabled for MDM</p>
              <p className="text-surface-500">Syncing via delta queries</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* iOS Calendar */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>iOS Calendar (EventKit)</CardTitle>
              <CardDescription>Native access via Capacitor on iOS device</CardDescription>
            </div>
            {iosConnected ? (
              <Button variant="secondary" onClick={() => setIosConnected(false)}>Disconnect</Button>
            ) : (
              <Button variant="primary" onClick={() => setIosConnected(true)}>Connect</Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {iosConnected && (
            <div className="space-y-2 text-sm">
              <p className="text-green-600 dark:text-green-400">✓ Connected</p>
              <p className="text-surface-500">Grant full calendar access in iOS Settings</p>
              <p className="text-surface-500">Background sync enabled</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Privacy & Categories */}
      <Card>
        <CardHeader>
          <CardTitle>Privacy & Categories</CardTitle>
          <CardDescription>Control which events are included in stress correlation</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { id: 'personal', label: 'Personal', default: false },
              { id: 'focus', label: 'Focus Time', default: false },
              { id: '1:1', label: '1:1 Meetings', default: true },
              { id: 'team', label: 'Team Meetings', default: true },
              { id: 'all-hands', label: 'All Hands', default: true },
              { id: 'external', label: 'External', default: true },
            ].map((cat) => (
              <label key={cat.id} className="flex items-center gap-2 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked={cat.default}
                  className="w-4 h-4 text-brand-500 border-surface-300 rounded focus:ring-brand-500"
                />
                <span className="text-sm">{cat.label}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
            <input
              type="checkbox"
              id="encrypt-calendar"
              defaultChecked={true}
              className="w-4 h-4 text-brand-500 border-surface-300 rounded focus:ring-brand-500"
            />
            <label htmlFor="encrypt-calendar" className="text-sm font-medium">
              Encrypt calendar tokens at rest
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Data Retention */}
      <Card>
        <CardHeader>
          <CardTitle>Data Retention</CardTitle>
          <CardDescription>Automatic cleanup of old calendar events</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
              <p className="font-medium text-surface-900 dark:text-surface-100">Raw Events</p>
              <p className="text-sm text-surface-500 dark:text-surface-400">90 days</p>
            </div>
            <div className="p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
              <p className="font-medium text-surface-900 dark:text-surface-100">Aggregated Scores</p>
              <p className="text-sm text-surface-500 dark:text-surface-400">1 year</p>
            </div>
          </div>
          <Button variant="secondary" onClick={() => window.open('/api/v1/calendar/export-correlation?format=csv', '_blank')}>
            Export Correlation Data
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}