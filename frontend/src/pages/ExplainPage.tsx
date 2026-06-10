import { useState } from 'react'

interface Factor {
  variable: string
  actual_value: number
  expected_value: number
  impact_pct: number
  direction: string
}

interface ExplanationResult {
  summary: string
  predicted_value: number
  actual_value: number
  deviation: number
  contributing_factors: Factor[]
  recommendation: string
}

export default function ExplainPage() {
  const [equation, setEquation] = useState('')
  const [actual, setActual] = useState('{"queue_depth": 95, "arrival_rate": 12.4, "service_rate": 1.2}')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ExplanationResult | null>(null)
  const [error, setError] = useState('')

  const handleExplain = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          equation: equation || '0.95 * arrival_rate - 1.21 * service_rate',
          actual: JSON.parse(actual),
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

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Explain Anomaly</h2>
      <p className="text-slate-400">Understand why actual values differ from predictions.</p>

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
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Actual Values (JSON)</label>
          <textarea
            value={actual}
            onChange={e => setActual(e.target.value)}
            rows={3}
            className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white font-mono text-sm"
          />
        </div>
        <button
          onClick={handleExplain}
          disabled={loading}
          className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-600 text-white font-medium px-6 py-2 rounded"
        >
          {loading ? 'Explaining...' : 'Explain'}
        </button>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>

      {result && (
        <div className="space-y-6">
          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-3">Summary</h3>
            <p className="text-slate-300">{result.summary}</p>
            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="bg-slate-900 rounded p-3 text-center">
                <p className="text-xs text-slate-400">Predicted</p>
                <p className="text-xl font-bold text-cyan-400">{result.predicted_value}</p>
              </div>
              <div className="bg-slate-900 rounded p-3 text-center">
                <p className="text-xs text-slate-400">Actual</p>
                <p className="text-xl font-bold text-white">{result.actual_value}</p>
              </div>
              <div className="bg-slate-900 rounded p-3 text-center">
                <p className="text-xs text-slate-400">Deviation</p>
                <p className={`text-xl font-bold ${result.deviation > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {result.deviation > 0 ? '+' : ''}{result.deviation}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-3">Contributing Factors</h3>
            <div className="space-y-3">
              {result.contributing_factors.map((f, i) => (
                <div key={i} className="bg-slate-900 rounded p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">{f.variable}</p>
                    <p className="text-xs text-slate-400">
                      Actual: {f.actual_value} vs Expected: {f.expected_value}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`font-mono font-bold ${f.impact_pct > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {f.impact_pct > 0 ? '+' : ''}{f.impact_pct}%
                    </p>
                    <p className="text-xs text-slate-400">{f.direction}</p>
                  </div>
                </div>
              ))}
            </div>
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
