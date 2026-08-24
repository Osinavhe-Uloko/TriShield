import { useState } from 'react'
import { submitFeedback } from '../api/client'

interface Props {
  scanId: string
}

export default function FeedbackButtons({ scanId }: Props) {
  const [sent, setSent] = useState<'phishing' | 'legitimate' | null>(null)

  async function send(verdict: 'phishing' | 'legitimate') {
    setSent(verdict)
    try {
      await submitFeedback(scanId, verdict)
    } catch {
      setSent(null)
    }
  }

  if (sent) {
    return <p className="text-sm text-slate-400">Thanks — feedback recorded as "{sent}".</p>
  }

  return (
    <div className="flex items-center gap-3 text-sm text-slate-400">
      <span>Was this verdict correct?</span>
      <button
        onClick={() => send('phishing')}
        className="rounded-lg border border-slate-700 px-3 py-1 hover:border-red-500/50 hover:text-red-300"
      >
        It's phishing
      </button>
      <button
        onClick={() => send('legitimate')}
        className="rounded-lg border border-slate-700 px-3 py-1 hover:border-emerald-500/50 hover:text-emerald-300"
      >
        It's legitimate
      </button>
    </div>
  )
}
