import { useState, useRef } from 'react'
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
  llm_explanation?: string
}

export default function DiscoverPage() {
  const [systemType, setSystemType] = useState('queue')
  const [target, setTarget] = useState('queue_depth')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ pareto: ParetoPoint[]; best: Equation | null } | null>(null)
  const [error, setError] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvPreview, setCsvPreview] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setCsvFile(file)
    const reader = new FileReader()
    reader.onload = (evt) => {
      const text = evt.target?.result as string
      setCsvPreview(text.split('\n').slice(0, 6))
      // Auto-detect target from header
      const header = text.split('\n')[0]
      if (header) {
        const cols = header.split(',').map(c => c.trim())
        const possible = cols.filter(c => c !== 't')
        if (possible.length > 0) setTarget(possible[0])
      }
    }
    reader.readAsText(file)
  }

  const handleDiscover = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const body: any = { target, max_generations: 50, population_size: 100 }

      if (csvFile) {
        body.csv_data = await csvFile.text()
      } else {
        body.system_type = systemType
      }

      const res = await fetch('/api/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Discovery failed')
      }
      const data = await res.json()
      const jobId = data.job_id

      let status
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const sRes = await fetch(`/api/discover/${jobId}/status`)
        status = await sRes.json()
        if (status.status === 'completed' || status.status === 'failed') break
      }

      if (status?.status === 'completed') {
        setResult({ pareto: status.pareto_front || [], best: status.best_equation || null })
      } else {
        setError(status?.error || 'Discovery failed or timed out')
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Data Source</label>
            <div className="flex gap-2">
              <select
                value={systemType}
                onChange={e => { setSystemType(e.target.value); setTarget(
                  e.target.value === 'queue' ? 'queue_depth' :
                  e.target.value === 'cpu' ? 'cpu_usage' :
                  e.target.value === 'db_connections' ? 'connections' : 'hit_rate'
                )}}
                disabled={!!csvFile}
                className="flex-1 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white disabled:opacity-50"
              >
                <option value="queue">Queue System</option>
                <option value="cpu">CPU Autoscaling</option>
                <option value="db_connections">DB Connections</option>
                <option value="cache">Cache Utilization</option>
              </select>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="bg-slate-600 hover:bg-slate-500 text-white px-4 py-2 rounded transition-colors text-sm whitespace-nowrap"
              >
                {csvFile ? 'Change CSV' : 'Upload CSV'}
              </button>
              {csvFile && (
                <button
                  onClick={() => { setCsvFile(null); setCsvPreview([]) }}
                  className="text-red-400 hover:text-red-300 text-sm px-2"
                >
                  Clear
                </button>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
            />
            {csvPreview.length > 0 && (
              <div className="mt-2 bg-slate-900 rounded p-2 text-xs font-mono text-slate-400 overflow-x-auto">
                {csvPreview.map((line, i) => (
                  <div key={i}>{line || '\u00A0'}</div>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Target Variable</label>
            <input
              value={target}
              onChange={e => setTarget(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono"
            />
          </div>
        </div>
        <button
          onClick={handleDiscover}
          disabled={loading}
          className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 text-white font-medium px-6 py-2 rounded transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Discovering...
            </span>
          ) : 'Run Discovery'}
        </button>
        {error && <p className="text-red-400 text-sm bg-red-900/30 rounded p-2">{error}</p>}
      </div>

      {loading && !result && (
        <div className="bg-slate-800 rounded-lg p-12 text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-slate-700 rounded w-3/4 mx-auto"></div>
            <div className="h-48 bg-slate-700 rounded"></div>
          </div>
        </div>
      )}

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Pareto Frontier ({result.pareto.length} points)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" dataKey="complexity" name="Complexity" stroke="#94a3b8" />
                <YAxis type="number" dataKey="mse" name="MSE" stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #475569' }}
                  formatter={(value: number, name: string) => [name === 'mse' ? value.toExponential(3) : value, name]}
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
                    <p className="text-white font-mono">{result.best.mse.toExponential(4)}</p>
                  </div>
                  <div className="bg-slate-900 rounded p-3">
                    <p className="text-slate-400">Complexity</p>
                    <p className="text-white font-mono">{result.best.complexity}</p>
                  </div>
                </div>
                <div className="bg-slate-900 rounded p-3">
                  <p className="text-slate-400 text-sm">Variables: {result.best.variables.join(', ')}</p>
                </div>
                {result.best.llm_explanation && (
                  <div className="bg-indigo-900/30 rounded p-4 border border-indigo-700/50">
                    <p className="text-xs text-indigo-300 mb-1 font-semibold">AI Analysis</p>
                    <p className="text-sm text-indigo-200">{result.best.llm_explanation}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
