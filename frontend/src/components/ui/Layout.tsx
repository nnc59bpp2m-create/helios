import { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="pt-14 lg:pt-0">
      <div className="p-4 lg:p-6">
        {children}
      </div>
    </div>
  )
}