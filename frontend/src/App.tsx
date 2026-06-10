import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import DiscoverPage from './pages/DiscoverPage'
import EquationsPage from './pages/EquationsPage'
import ForecastPage from './pages/ForecastPage'
import ExplainPage from './pages/ExplainPage'
import SimulatePage from './pages/SimulatePage'

const navItems = [
  { path: '/', label: 'Discover' },
  { path: '/equations', label: 'Equations' },
  { path: '/forecast', label: 'Forecast' },
  { path: '/explain', label: 'Explain' },
  { path: '/simulate', label: 'Simulate' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <nav className="bg-slate-800 border-b border-slate-700 px-6 py-3">
          <div className="flex items-center gap-8">
            <h1 className="text-xl font-bold text-cyan-400">EquationX</h1>
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive ? 'text-cyan-400' : 'text-slate-400 hover:text-white'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<DiscoverPage />} />
            <Route path="/equations" element={<EquationsPage />} />
            <Route path="/forecast" element={<ForecastPage />} />
            <Route path="/explain" element={<ExplainPage />} />
            <Route path="/simulate" element={<SimulatePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
