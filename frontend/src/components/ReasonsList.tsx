interface Props {
  reasons: string[]
}

export default function ReasonsList({ reasons }: Props) {
  if (!reasons.length) return null
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Why this verdict
      </h3>
      <ul className="space-y-1.5">
        {reasons.map((reason, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
            {reason}
          </li>
        ))}
      </ul>
    </div>
  )
}
