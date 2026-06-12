import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { Header } from './components/ui/Header'
import { Sidebar } from './components/ui/Sidebar'
import { ThemeProvider } from './context/ThemeContext'
import { GlobalFilterProvider } from './context/GlobalFilterContext'
import { Layout } from './components/ui/Layout'
import { LoadingSpinner } from './components/ui/LoadingSpinner'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'))
const HeartRate = lazy(() => import('./pages/HeartRate'))
const HRV = lazy(() => import('./pages/HRV'))
const SpO2 = lazy(() => import('./pages/SpO2'))
const SkinTemperature = lazy(() => import('./pages/SkinTemperature'))
const EDA = lazy(() => import('./pages/EDA'))
const Sleep = lazy(() => import('./pages/Sleep'))
const Activity = lazy(() => import('./pages/Activity'))
const Coach = lazy(() => import('./pages/Coach'))
const StressCalendar = lazy(() => import('./pages/StressCalendar'))
const StressLeaderboard = lazy(() => import('./pages/StressLeaderboard'))
const Settings = lazy(() => import('./pages/Settings'))
const CalendarSettings = lazy(() => import('./pages/CalendarSettings'))

function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      {children}
    </Suspense>
  )
}

function App() {
  return (
    <ThemeProvider>
      <GlobalFilterProvider>
        <div className="min-h-screen bg-surface-50 dark:bg-surface-950">
          <Header />
          <div className="flex">
            <Sidebar />
            <main className="flex-1 lg:ml-64 min-h-[calc(100vh-4rem)]">
              <Layout>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route
                    path="/dashboard"
                    element={
                      <PageWrapper>
                        <Dashboard />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/heart-rate"
                    element={
                      <PageWrapper>
                        <HeartRate />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/hrv"
                    element={
                      <PageWrapper>
                        <HRV />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/spo2"
                    element={
                      <PageWrapper>
                        <SpO2 />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/skin-temperature"
                    element={
                      <PageWrapper>
                        <SkinTemperature />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/eda"
                    element={
                      <PageWrapper>
                        <EDA />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/sleep"
                    element={
                      <PageWrapper>
                        <Sleep />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/activity"
                    element={
                      <PageWrapper>
                        <Activity />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/coach"
                    element={
                      <PageWrapper>
                        <Coach />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/stress-calendar"
                    element={
                      <PageWrapper>
                        <StressCalendar />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/stress-leaderboard"
                    element={
                      <PageWrapper>
                        <StressLeaderboard />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <PageWrapper>
                        <Settings />
                      </PageWrapper>
                    }
                  />
                  <Route
                    path="/settings/calendar"
                    element={
                      <PageWrapper>
                        <CalendarSettings />
                      </PageWrapper>
                    }
                  />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </Layout>
            </main>
          </div>
        </div>
      </GlobalFilterProvider>
    </ThemeProvider>
  )
}

export default App