import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { getAnalyticsSummary, type AnalyticsSummary } from '../api/client'

const PIE_COLORS = ['#f87171', '#34d399']

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-100">{value}</div>
    </div>
  )
}

export default function Analytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getAnalyticsSummary()
      .then(setSummary)
      .catch(() => setError('Could not load analytics.'))
  }, [])

  if (error) return <p className="px-6 py-10 text-sm text-red-400">{error}</p>
  if (!summary) return <p className="px-6 py-10 text-sm text-slate-500">Loading…</p>

  const channelData = Object.entries(summary.by_channel).map(([name, count]) => ({ name, count }))
  const verdictData = [
    { name: 'Phishing', value: summary.phishing_count },
    { name: 'Legitimate', value: summary.legitimate_count },
  ]
  const dailyData = Object.entries(summary.scans_last_7_days)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, count]) => ({ date: date.slice(5), count }))

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Analytics</h1>
        <p className="mt-1 text-sm text-slate-400">Model performance & usage at a glance.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Total scans" value={summary.total_scans.toLocaleString()} />
        <StatTile label="Flagged phishing" value={summary.phishing_count.toLocaleString()} />
        <StatTile label="Avg. confidence" value={`${(summary.average_confidence * 100).toFixed(1)}%`} />
        <StatTile
          label="Feedback accuracy"
          value={summary.feedback_accuracy === null ? '—' : `${(summary.feedback_accuracy * 100).toFixed(1)}%`}
        />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Scans by channel</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={channelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b' }} />
              <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Verdict split</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={verdictData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                {verdictData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">Scans, last 7 days</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={dailyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
            <YAxis stroke="#64748b" fontSize={12} allowDecimals={false} />
            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b' }} />
            <Bar dataKey="count" fill="#a78bfa" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
