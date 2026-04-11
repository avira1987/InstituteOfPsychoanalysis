import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { getRouterBasename } from './utils/routerBasename'
import PersianDigitsBoundary from './components/PersianDigitsBoundary'
import App from './App'
import './styles/global.css'

const basename = getRouterBasename() || undefined

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <PersianDigitsBoundary>
          <App />
        </PersianDigitsBoundary>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)
