import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import './index.css'
// Importing the stores first wires them into the API client before any request.
import '@/stores/auth'
import '@/stores/language'
import { Providers } from '@/app/providers'
import { router } from '@/app/router'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
)
