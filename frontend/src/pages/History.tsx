import { useEffect, useState } from 'react'
import { getHistory, type ScanHistoryItem } from '../api/client'
import { riskColor } from '../components/RiskBadge'

export default function History() {
  const [items, setItems] = useState<ScanHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHistory()
      .then(setItems)
      .catch(() => setError('Could not load scan history.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Scan history</h1>
        <p className="mt-1 text-sm text-slate-400">Recent scans across all channels.</p>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-slate-500">No scans yet — run one from the Scan tab.</p>
      )}

      {items.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800/60 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Input</th>
                <th className="px-4 py-3">Verdict</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Scanned</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const c = riskColor(item.risk_score)
                return (
                  <tr key={item.id} className="border-t border-slate-800/60 hover:bg-slate-800/30">
                    <td className="px-4 py-3 uppercase text-slate-400">{item.input_type}</td>
                    <td className="max-w-xs truncate px-4 py-3 font-mono text-slate-300">{item.input_raw}</td>
                    <td className={`px-4 py-3 font-medium ${c.text}`}>{item.verdict}</td>
                    <td className="px-4 py-3 text-slate-300">{(item.risk_score * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-slate-300">{(item.confidence * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-slate-500">{new Date(item.created_at).toLocaleString()}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
