import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { SimulatedSmsProvider } from './contexts/SimulatedSmsContext'
import { getRouterBasename } from './utils/routerBasename'
import PersianDigitsBoundary from './components/PersianDigitsBoundary'
import App from './App'
import { initClientObservability } from './observability/sentryClient'
/* باندل محلی — بدون وابستگی به cdn.jsdelivr (کند/فیلتر در برخی شبکه‌ها) */
import '@fontsource-variable/vazirmatn/wght.css'
import './styles/global.css'

initClientObservability()

const basename = getRouterBasename() || undefined

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <ToastProvider>
          <SimulatedSmsProvider>
            <PersianDigitsBoundary>
              <App />
            </PersianDigitsBoundary>
          </SimulatedSmsProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)
