import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('UI crashed:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="flex h-full min-h-48 w-full flex-col items-center justify-center gap-2 rounded-[3px] border border-fail/40 bg-fail-soft p-6 text-center text-ink">
          <p className="font-display text-xl font-semibold">{this.props.title ?? 'This part of the page failed to load'}</p>
          <p className="max-w-md text-sm text-graphite">{String(this.state.error.message ?? this.state.error)}</p>
          <button onClick={() => this.setState({ error: null })} className="btn btn-ghost mt-2">Try again</button>
        </div>
      )
    }
    return this.props.children
  }
}
