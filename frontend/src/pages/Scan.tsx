import { useState } from 'react'
import { predictUrl, predictEmail, predictWebpage, type PredictResponse } from '../api/client'
import RiskBadge from '../components/RiskBadge'
import ReasonsList from '../components/ReasonsList'
import FeatureBreakdown from '../components/FeatureBreakdown'
import FeedbackButtons from '../components/FeedbackButtons'

type Channel = 'url' | 'email' | 'webpage'

const CHANNEL_LABEL: Record<Channel, string> = {
  url: 'URL',
  email: 'Email',
  webpage: 'Webpage',
}

const PLACEHOLDER: Record<Channel, string> = {
  url: 'https://example.com/login',
  email: 'Paste raw email source (headers + body)…',
  webpage: 'https://example.com',
}

export default function Scan() {
  const [channel, setChannel] = useState<Channel>('url')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PredictResponse | null>(null)

  async function handleScan() {
    if (!input.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let res: PredictResponse
      if (channel === 'url') res = await predictUrl(input.trim())
      else if (channel === 'email') res = await predictEmail(input)
      else res = await predictWebpage(input.trim())
      setResult(res)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Scan failed. Check the input and try again.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">Scan for phishing</h1>
        <p className="mt-1 text-sm text-slate-400">
          Paste a URL, raw email, or webpage address to get an instant, explainable verdict.
        </p>
      </div>

      <div className="flex gap-1 rounded-xl bg-slate-800/60 p-1">
        {(Object.keys(CHANNEL_LABEL) as Channel[]).map((c) => (
          <button
            key={c}
            onClick={() => {
              setChannel(c)
              setResult(null)
              setError(null)
            }}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition ${
              channel === c ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {CHANNEL_LABEL[c]}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {channel === 'email' ? (
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={PLACEHOLDER[channel]}
            rows={8}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/60 p-4 font-mono text-sm text-slate-200 placeholder:text-slate-600 focus:border-sky-500 focus:outline-none"
          />
        ) : (
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={PLACEHOLDER[channel]}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-sm text-slate-200 placeholder:text-slate-600 focus:border-sky-500 focus:outline-none"
          />
        )}
        <button
          onClick={handleScan}
          disabled={loading || !input.trim()}
          className="w-full rounded-xl bg-sky-500 py-3 text-sm font-semibold text-white transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? 'Analyzing…' : `Scan ${CHANNEL_LABEL[channel]}`}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <RiskBadge verdict={result.verdict} riskScore={result.risk_score} />
            <div className="text-right text-xs text-slate-500">
              <div>confidence {(result.confidence * 100).toFixed(1)}%</div>
              <div>{result.latency_ms.toFixed(0)}ms · model v{result.model_version}</div>
            </div>
          </div>

          <ReasonsList reasons={result.reasons} />
          <FeatureBreakdown features={result.feature_breakdown} />
          <FeedbackButtons scanId={result.scan_id} />
        </div>
      )}
    </div>
  )
}
