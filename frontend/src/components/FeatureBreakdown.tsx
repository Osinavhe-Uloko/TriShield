import { useState } from 'react'

interface Props {
  features: Record<string, number>
}

export default function FeatureBreakdown({ features }: Props) {
  const [open, setOpen] = useState(false)
  const entries = Object.entries(features)
  if (!entries.length) return null

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-sm font-semibold uppercase tracking-wide text-slate-400"
      >
        Feature breakdown ({entries.length})
        <span>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="mt-3 grid max-h-64 grid-cols-2 gap-x-6 gap-y-1 overflow-y-auto text-xs sm:grid-cols-3">
          {entries.map(([name, value]) => (
            <div key={name} className="flex justify-between gap-2 border-b border-slate-800 py-1">
              <span className="truncate text-slate-500">{name}</span>
              <span className="font-mono text-slate-300">{typeof value === 'number' ? value.toFixed(2) : String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
