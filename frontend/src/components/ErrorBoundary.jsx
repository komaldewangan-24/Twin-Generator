import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Viewer crashed:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full min-h-40 w-full flex-col items-center justify-center gap-2 rounded-xl bg-slate-950 p-6 text-center text-slate-400">
          <span className="text-3xl">⚠️</span>
          <p className="max-w-md text-sm">
            The 3D viewer hit an error: <span className="text-red-400">{String(this.state.error.message ?? this.state.error)}</span>
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded-lg border border-slate-700 px-4 py-1.5 text-xs text-slate-300 transition hover:border-emerald-500 hover:text-emerald-300"
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}