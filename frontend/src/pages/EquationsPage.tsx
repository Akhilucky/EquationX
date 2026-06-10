import { useState, useEffect } from 'react'

interface Equation {
  id: string
  latex: string
  complexity: number
  mse: number
  variables: string[]
  target: string
  job_id?: string
}

export default function EquationsPage() {
  const [equations, setEquations] = useState<Equation[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('/api/equations')
      .then(r => r.json())
      .then(setEquations)
      .catch(() => {})
  }, [])

  const filtered = equations.filter(e =>
    e.latex.toLowerCase().includes(search.toLowerCase()) ||
    e.target.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Discovered Equations</h2>

      <div className="bg-slate-800 rounded-lg p-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search equations..."
          className="w-full bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white"
        />
      </div>

      {filtered.length === 0 ? (
        <div className="bg-slate-800 rounded-lg p-12 text-center text-slate-400">
          No equations discovered yet. Run discovery first.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(eq => (
            <div key={eq.id} className="bg-slate-800 rounded-lg p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-400">{eq.id}</span>
                <span className="text-xs bg-cyan-900 text-cyan-300 px-2 py-0.5 rounded">{eq.target}</span>
              </div>
              <div className="bg-slate-900 rounded p-3">
                <p className="text-cyan-300 font-mono text-xs break-all">{eq.latex}</p>
              </div>
              <div className="flex gap-4 text-xs text-slate-400">
                <span>MSE: <span className="text-white font-mono">{eq.mse.toFixed(6)}</span></span>
                <span>Complexity: <span className="text-white font-mono">{eq.complexity}</span></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
