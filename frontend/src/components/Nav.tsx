import { NavLink } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'

const links = [
  { to: '/', label: 'Scan' },
  { to: '/history', label: 'History' },
  { to: '/analytics', label: 'Analytics' },
]

export default function Nav() {
  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/60">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          <span className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">TriShield</span>
        </div>
        <div className="flex items-center gap-2">
          <nav className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-transparent dark:p-0">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `rounded-lg px-2.5 py-1.5 text-sm font-medium transition sm:px-3 ${
                    isActive
                      ? 'bg-white text-sky-600 shadow-sm dark:bg-sky-500/15 dark:text-sky-300 dark:shadow-none'
                      : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
