import { useState } from 'react'
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ComposedChart } from 'recharts'

interface ForecastPoint {
  time_minutes: number
  value: number
  lower_ci: number
  upper_ci: number
}

interface ForecastResult {
  trajectory: ForecastPoint[]
  threshold_breach: boolean
  time_to_breach_minutes: number | null
  peak_value: number
  steady_state_value: number
}

export default function ForecastPage() {
  const [equation, setEquation] = useState('')
  const [initial, setInitial] = useState('{"queue_depth": 10, "arrival_rate": 8.0, "service_rate": 1.0}')
  const [threshold, setThreshold] = useState('')
  const [horizon, setHorizon] = useState(15)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ForecastResult | null>(null)
  const [error, setError] = useState('')

  const handleForecast = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const body: any = {
        equation: equation || '0.95 * arrival_rate - 1.21 * service_rate',
        initial_conditions: JSON.parse(initial),
        horizon_minutes: horizon,
      }
      if (threshold) body.threshold = parseFloat(threshold)

      const res = await fetch('/api/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Forecast failed')
      }
      const data = await res.json()

      const mappedTrajectory = (data.trajectory || []).map((pt: any) => ({
        time_minutes: pt.time_minutes ?? pt.time,
        value: pt.value,
        lower_ci: pt.lower_ci ?? (pt.ci ? pt.ci[0] : pt.value),
        upper_ci: pt.upper_ci ?? (pt.ci ? pt.ci[1] : pt.value),
      }))

      setResult({
        trajectory: mappedTrajectory,
        threshold_breach: data.threshold_breach,
        time_to_breach_minutes: data.time_to_breach_minutes,
        peak_value: data.peak_value,
        steady_state_value: data.steady_state_value,
      })
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const chartData = result?.trajectory.map(pt => ({
    time: pt.time_minutes,
    value: pt.value,
    lower: pt.lower_ci,
    upper: pt.upper_ci,
  })) || []

  const thresholdVal = threshold ? parseFloat(threshold) : undefined

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Forecast</h2>
      <p className="text-slate-400">Predict future values with confidence intervals and detect threshold breaches.</p>

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
            <label className="block text-sm font-medium text-slate-300 mb-1">Initial Conditions (JSON)</label>
            <input
              value={initial}
              onChange={e => setInitial(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Threshold</label>
            <input
              value={threshold}
              onChange={e => setThreshold(e.target.value)}
              placeholder="100"
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
          onClick={handleForecast}
          disabled={loading}
          className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 text-white font-medium px-6 py-2 rounded transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Forecasting...
            </span>
          ) : 'Run Forecast'}
        </button>
        {error && <p className="text-red-400 text-sm bg-red-900/30 rounded p-2">{error}</p>}
      </div>

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400">Peak Value</p>
              <p className="text-2xl font-bold text-white">{result.peak_value}</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-sm text-slate-400">Steady State</p>
              <p className="text-2xl font-bold text-white">{result.steady_state_value}</p>
            </div>
            <div className={`bg-slate-800 rounded-lg p-4 ${result.threshold_breach ? 'border border-red-500' : ''}`}>
              <p className="text-sm text-slate-400">Threshold Breach</p>
              <p className={`text-2xl font-bold ${result.threshold_breach ? 'text-red-400' : 'text-green-400'}`}>
                {result.threshold_breach ? `t=${result.time_to_breach_minutes?.toFixed(1)} min` : 'None'}
              </p>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Trajectory with Confidence Intervals</h3>
            <ResponsiveContainer width="100%" height={350}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94a3b8" label={{ value: 'Minutes', position: 'bottom' }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #475569' }} />
                {thresholdVal && <ReferenceLine y={thresholdVal} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Threshold', fill: '#ef4444' }} />}
                <Area type="monotone" dataKey="upper" stroke="none" fill="#22d3ee" fillOpacity={0.1} />
                <Area type="monotone" dataKey="lower" stroke="none" fill="#0f172a" fillOpacity={1} />
                <Line type="monotone" dataKey="value" stroke="#22d3ee" strokeWidth={2} dot={false} name="Predicted" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
