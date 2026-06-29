import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

const navItems = [
  { to: '/', label: '🏠 Dashboard' },
  { to: '/run-pipeline', label: '🚀 Run Pipeline' },
  { to: '/requirements', label: '✍️ Requirements' },
  { to: '/test-cases', label: '📋 Test Cases' },
  { to: '/test-results', label: '📊 Test Results' },
  { to: '/coverage', label: '📈 Coverage Report' },
  { to: '/agent-activity', label: '🤖 Agent Activity' },
]

export default function Sidebar() {
  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
    }
    return false
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <aside className="w-64 flex-shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-xl font-bold">🧪 AetherTest</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Multi-Agent AI Testing Platform
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto" aria-label="Main navigation">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700 space-y-2">
        <button
          onClick={() => setDark(!dark)}
          className="w-full px-3 py-2 text-sm rounded-md bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          aria-label="Toggle dark mode"
        >
          {dark ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </button>
        <div className="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
          <p><strong>Region:</strong> us-east-1</p>
          <p><strong>Model:</strong> Claude Sonnet 4</p>
        </div>
      </div>
    </aside>
  )
}
