import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ChartProvider } from './providers/chart-provider'
import { HumanFactorsProvider } from './providers/human-factors-provider'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ChartProvider>
        <HumanFactorsProvider>
          <App />
        </HumanFactorsProvider>
      </ChartProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
