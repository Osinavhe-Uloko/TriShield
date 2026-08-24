interface Props {
  verdict: string
  riskScore: number
}

export function riskColor(riskScore: number): { bg: string; text: string; label: string } {
  if (riskScore >= 0.66) return { bg: 'bg-red-500/15 border-red-500/40', text: 'text-red-400', label: 'High risk' }
  if (riskScore >= 0.33) return { bg: 'bg-amber-500/15 border-amber-500/40', text: 'text-amber-400', label: 'Medium risk' }
  return { bg: 'bg-emerald-500/15 border-emerald-500/40', text: 'text-emerald-400', label: 'Low risk' }
}

export default function RiskBadge({ verdict, riskScore }: Props) {
  const c = riskColor(riskScore)
  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium ${c.bg} ${c.text}`}>
      <span className="h-2 w-2 rounded-full bg-current" />
      {verdict === 'phishing' ? 'Phishing' : 'Legitimate'} · {c.label} ({(riskScore * 100).toFixed(1)}%)
    </div>
  )
}
