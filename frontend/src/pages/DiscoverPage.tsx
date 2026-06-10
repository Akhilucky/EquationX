import { useState } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface ParetoPoint {
  complexity: number
  mse: number
  latex: string
  equation_id: string
}

interface Equation {
  id: string
  latex: string
  complexity: number
  mse: number
  variables: string[]
  target: string
}

export default function DiscoverPage() {
  const [systemType, setSystemType] = useState('queue')
  const [target, setTarget] = useState('queue_depth')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ pareto: ParetoPoint[]; best: Equation | null } | null>(null)
  const [error, setError] = useState('')

  const handleDiscover = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_type: systemType, target, max_generations: 50, population_size: 100 }),
      })
      const data = await res.json()
      const jobId = data.job_id

      // Poll status
      let status
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const sRes = await fetch(`/api/discover/${jobId}/status`)
        status = await sRes.json()
        if (status.status === 'completed' || status.status === 'failed') break
      }

      if (status?.status === 'completed') {
        setResult({ pareto: status.pareto_front || [], best: status.best_equation })
      } else {
        setError(status?.error || 'Discovery failed')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Equation Discovery</h2>
      <p className="text-slate-400">Upload CSV or use synthetic data to discover mathematical laws governing your infrastructure.</p>

      <div className="bg-slate-800 rounded-lg p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">System Type</label>
            <select
              value={systemType}
              onChange={e => { setSystemType(e.target.value); setTarget(
                e.target.value === 'queue' ? 'queue_depth' :
                e.target.value === 'cpu' ? 'cpu_usage' :
                e.target.value === 'db_connections' ? 'connections' : 'hit_rate'
              )}}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
            >
              <option value="queue">Queue System</option>
              <option value="cpu">CPU Autoscaling</option>
              <option value="db_connections">DB Connections</option>
              <option value="cache">Cache Utilization</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Target Variable</label>
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
            />
          </div>
        </div>
        <button
          onClick={handleDiscover}
          disabled={loading}
          className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 text-white font-medium px-6 py-2 rounded transition-colors"
        >
          {loading ? 'Discovering...' : 'Run Discovery'}
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Pareto Frontier</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" dataKey="complexity" name="Complexity" stroke="#94a3b8" />
                <YAxis type="number" dataKey="mse" name="MSE" stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #475569' }}
                  formatter={(value: number, name: string) => [name === 'mse' ? value.toFixed(6) : value, name]}
                />
                <Scatter data={result.pareto} fill="#22d3ee" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {result.best && (
            <div className="bg-slate-800 rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Best Equation</h3>
              <div className="space-y-3">
                <div className="bg-slate-900 rounded p-4">
                  <p className="text-xs text-slate-400 mb-1">LaTeX</p>
                  <p className="text-cyan-300 font-mono text-sm break-all">{result.best.latex}</p>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-slate-900 rounded p-3">
                    <p className="text-slate-400">MSE</p>
                    <p className="text-white font-mono">{result.best.mse.toFixed(6)}</p>
                  </div>
                  <div className="bg-slate-900 rounded p-3">
                    <p className="text-slate-400">Complexity</p>
                    <p className="text-white font-mono">{result.best.complexity}</p>
                  </div>
                </div>
                <div className="bg-slate-900 rounded p-3">
                  <p className="text-slate-400 text-sm">Variables: {result.best.variables.join(', ')}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
