import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { createAuthClient } from '@auth-kit/react/client'
import { AuthProvider } from '@auth-kit/react/react'
import { AuthUIProvider } from '@auth-kit/react/ui'
import '@auth-kit/react/ui/styles.css'

import { App } from './App'
import './dari.css'

// Même origine que l'API : /api est relayé vers le backend (proxy Vite en dev, Nginx en production)
const authClient = createAuthClient({ baseUrl: import.meta.env.VITE_API_BASE ?? '/api' })

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Une erreur 4xx ne se règle pas en réessayant
      retry: (count, error) => count < 2 && !('status' in error && Number(error.status) >= 400),
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider client={authClient}>
        <AuthUIProvider brand={{ name: 'Dari' }} messages={{ login: { title: 'Connexion à Dari' } }}>
          <App />
        </AuthUIProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
