import { createBrowserRouter, RouterProvider } from 'react-router'

import { createAuthRoutes } from '@auth-kit/react/ui'

import { Layout } from './Layout'
import { AccueilPage } from './pages/AccueilPage'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <AccueilPage /> },
      ...createAuthRoutes(),
    ],
  },
])

export function App() {
  return <RouterProvider router={router} />
}
