import { useTheme } from '../../context/ThemeContext'
import { useGlobalFilter } from '../../context/GlobalFilterContext'
import { useState } from 'react'
import { Sun, Moon, Calendar, ChevronDown, Menu, X, Bluetooth, Wifi, Zap } from 'lucide-react'
import { clsx } from 'clsx'

export function Header() {
  const { theme, toggleTheme } = useTheme()
  const { dateRange, deviceId, preset, setPreset } = useGlobalFilter()
  const [showPresets, setShowPresets] = useState(false)
  const [showDeviceMenu, setShowDeviceMenu] = useState(false)

  const PRESETS = {
    '7d': 'Last 7 days',
    '30d': 'Last 30 days',
    '90d': 'Last 90 days',
    '1y': 'Last year'
  }

  const formatDate = (date?: Date) => {
    if (!date) return 'All time'
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-14 bg-white/80 dark:bg-surface-950/80 backdrop-blur-sm border-b border-surface-200 dark:border-surface-800">
      <div className="flex items-center justify-between h-full px-4 lg:px-6">
        <div className="flex items-center gap-4">
          <button className="lg:hidden btn-ghost p-2" aria-label="Toggle menu">
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2">
            <Zap className="w-7 h-7 text-brand-500" />
            <span className="text-xl font-bold text-surface-900 dark:text-surface-100">Helios</span>
          </div>
        </div>

        <div className="flex items-center gap-2 lg:gap-4">
          {/* Date Range Picker */}
          <div className="relative">
            <button
              className="btn-secondary px-3 py-1.5 text-sm gap-1"
              onClick={() => setShowPresets(!showPresets)}
              aria-expanded={showPresets}
            >
              <Calendar className="w-4 h-4" />
              <span className="hidden sm:inline">
                {preset && PRESETS[preset as keyof typeof PRESETS] ? PRESETS[preset as keyof typeof PRESETS] : formatDate(dateRange.from)}
              </span>
              <ChevronDown className={clsx('w-3 h-3 transition-transform', showPresets && 'rotate-180')} />
            </button>

            {showPresets && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowPresets(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 card min-w-[180px] py-1 shadow-lg animate-in">
                  {Object.entries(PRESETS).map(([key, label]) => (
                    <button
                      key={key}
                      className={clsx('w-full px-3 py-2 text-left text-sm', preset === key ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300' : 'hover:bg-surface-100 dark:hover:bg-surface-800')}
                      onClick={() => { setPreset(key); setShowPresets(false); }}
                    >
                      {label}
                    </button>
                  ))}
                  <hr className="my-1 border-surface-200 dark:border-surface-700" />
                  <button
                    className="w-full px-3 py-2 text-left text-sm text-brand-600 dark:text-brand-400 hover:bg-surface-100 dark:hover:bg-surface-800"
                    onClick={() => { setPreset('custom'); setShowPresets(false); }}
                  >
                    Custom range...
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Device Selector */}
          <div className="relative hidden sm:block">
            <button
              className="btn-secondary px-3 py-1.5 text-sm gap-1"
              onClick={() => setShowDeviceMenu(!showDeviceMenu)}
              aria-expanded={showDeviceMenu}
            >
              <Bluetooth className="w-4 h-4" />
              <span>{deviceId || 'Select device'}</span>
              <ChevronDown className={clsx('w-3 h-3 transition-transform', showDeviceMenu && 'rotate-180')} />
            </button>

            {showDeviceMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowDeviceMenu(false)} />
                <div className="absolute right-0 top-full mt-1 z-50 card min-w-[200px] py-1 shadow-lg animate-in">
                  <button
                    className={clsx('w-full px-3 py-2 text-left text-sm', !deviceId ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300' : 'hover:bg-surface-100 dark:hover:bg-surface-800')}
                    onClick={() => { /* TODO: setDeviceId(null) */ setShowDeviceMenu(false); }}
                  >
                    All devices
                  </button>
                  <hr className="my-1 border-surface-200 dark:border-surface-700" />
                  <div className="px-3 py-2 text-xs text-surface-500 dark:text-surface-400">
                    No devices connected
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Theme Toggle */}
          <button
            className="btn-ghost p-2"
            onClick={toggleTheme}
            aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          >
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </button>
        </div>
      </div>
    </header>
  )
}