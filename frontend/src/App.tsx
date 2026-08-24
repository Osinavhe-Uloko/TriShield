import { Routes, Route } from 'react-router-dom'
import Nav from './components/Nav'
import Scan from './pages/Scan'
import History from './pages/History'
import Analytics from './pages/Analytics'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Scan />} />
          <Route path="/history" element={<History />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </main>
    </div>
  )
}
