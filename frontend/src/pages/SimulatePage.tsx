import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface ForecastPoint {
  time_minutes: number
  value: number
}

interface SimulateResult {
  baseline_trajectory: ForecastPoint[]
  modified_trajectory: ForecastPoint[]
  peak_value: number
  steady_state_value: number
  time_to_stabilize_minutes: number
  threshold_breach: boolean
  recommendation: string
}

export default function SimulatePage() {
  const [equation, setEquation] = useState('')
  const [changes, setChanges] = useState('{"service_rate": 16}')
  const [initial, setInitial] = useState('{"queue_depth": 10}')
  const [horizon, setHorizon] = useState(60)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SimulateResult | null>(null)
  const [error, setError] = useState('')

  const handleSimulate = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          equation: equation || '0.95 * arrival_rate - 1.21 * service_rate',
          parameter_changes: JSON.parse(changes),
          initial_conditions: JSON.parse(initial),
          horizon_minutes: horizon,
        }),
      })
      const data = await res.json()
      setResult(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const chartData = result
    ? result.baseline_trajectory.map((bp, i) => ({
        time: bp.time_minutes,
        baseline: bp.value,
        modified: result.modified_trajectory[i]?.value ?? bp.value,
      }))
    : []

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">What-If Simulation</h2>
      <p className="text-slate-400">Modify parameters and see how the system responds.</p>

      <div className="bg-slate-800 rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Equation (LaTeX)</label>
          <input
            value={equation}
            onChange={e => setEquation(e.target.value)}
            placeholder="0.95 * arrival_rate - 1.21 * service_rate"
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
          />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Parameter Changes (JSON)</label>
            <input
              value={changes}
              onChange={e => setChanges(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Initial Conditions (JSON)</label>
            <input
              value={initial}
              onChange={e => setInitial(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Horizon (min)</label>
            <input
              type="number"
              value={horizon}
              onChange={e => setHorizon(parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
            />
          </div>
        </div>
        <button
          onClick={handleSimulate}
          disabled={loading}
          className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 text-white font-medium px-6 py-2 rounded"
        >
          {loading ? 'Simulating...' : 'Run Simulation'}
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400">Peak</p>
              <p className="text-2xl font-bold text-white">{result.peak_value}</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400">Steady State</p>
              <p className="text-2xl font-bold text-white">{result.steady_state_value}</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400">Stabilize Time</p>
              <p className="text-2xl font-bold text-white">{result.time_to_stabilize_minutes} min</p>
            </div>
            <div className={`bg-slate-800 rounded-lg p-4 ${result.threshold_breach ? 'border border-red-500' : ''}`}>
              <p className="text-sm text-slate-400">Threshold Breach</p>
              <p className={`text-2xl font-bold ${result.threshold_breach ? 'text-red-400' : 'text-green-400'}`}>
                {result.threshold_breach ? 'Yes' : 'No'}
              </p>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Trajectory Comparison</h3>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94a3b8" label={{ value: 'Minutes', position: 'bottom' }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                <Legend />
                <Line type="monotone" dataKey="baseline" stroke="#64748b" strokeWidth={2} dot={false} name="Baseline" />
                <Line type="monotone" dataKey="modified" stroke="#22d3ee" strokeWidth={2} dot={false} name="Modified" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-3">Recommendation</h3>
            <p className="text-cyan-300">{result.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  )
}
