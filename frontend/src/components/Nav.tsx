import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Scan' },
  { to: '/history', label: 'History' },
  { to: '/analytics', label: 'Analytics' },
]

export default function Nav() {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          <span className="text-lg font-semibold tracking-tight text-slate-100">TriShield</span>
        </div>
        <nav className="flex gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  isActive ? 'bg-sky-500/15 text-sky-300' : 'text-slate-400 hover:text-slate-200'
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
