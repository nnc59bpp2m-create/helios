import { NavLink, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  LayoutDashboard,
  Activity,
  HeartPulse,
  Brain,
  Calendar,
  Trophy,
  Settings,
  Moon,
  Sun,
  Zap
} from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Heart Rate', href: '/heart-rate', icon: HeartPulse },
  { name: 'HRV', href: '/hrv', icon: Activity },
  { name: 'SpO₂', href: '/spo2', icon: Zap },
  { name: 'Skin Temp', href: '/skin-temperature', icon: Moon },
  { name: 'EDA / Stress', href: '/eda', icon: Brain },
  { name: 'Sleep', href: '/sleep', icon: Moon },
  { name: 'Activity', href: '/activity', icon: Activity },
  { name: 'AI Coach', href: '/coach', icon: Brain },
  { name: 'Stress Calendar', href: '/stress-calendar', icon: Calendar },
  { name: 'Stress Leaderboard', href: '/stress-leaderboard', icon: Trophy },
  { name: 'Settings', href: '/settings', icon: Settings }
]

export function Sidebar() {
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()

  return (
    <aside className="fixed lg:static inset-y-0 left-0 z-50 w-64 bg-white dark:bg-surface-950 border-r border-surface-200 dark:border-surface-800 transform transition-transform duration-300 lg:translate-x-0">
      <div className="flex flex-col h-full">
        <div className="flex flex-col h-full pt-14 lg:pt-0">
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href ||
                (item.href !== '/dashboard' && location.pathname.startsWith(item.href))
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={({ isActive: active }) => clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    active
                      ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300'
                      : 'text-surface-600 hover:bg-surface-100 dark:text-surface-400 dark:hover:bg-surface-800'
                  )}
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {item.name}
                </NavLink>
              )
            })}
          </nav>

          <div className="p-3 border-t border-surface-200 dark:border-surface-800">
            <button
              onClick={toggleTheme}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-surface-600 hover:bg-surface-100 dark:text-surface-400 dark:hover:bg-surface-800 transition-colors"
            >
              {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}