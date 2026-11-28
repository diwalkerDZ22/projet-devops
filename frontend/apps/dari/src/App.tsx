import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { createAuthRoutes, FullPageSpinner } from '@auth-kit/react/ui'

import { Layout } from './Layout'
import { AccueilPage } from './pages/AccueilPage'

// Pages chargées à la demande : le bundle initial reste léger
const IntrouvablePage = lazy(() => import('./pages/IntrouvablePage'))

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <AccueilPage /> },
      ...createAuthRoutes(),
      { path: '*', element: <Suspense fallback={<FullPageSpinner />}><IntrouvablePage /></Suspense> },
    ],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
