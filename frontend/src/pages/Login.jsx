import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { Spinner } from '../components/ui'
import { apiErrorMessage } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not sign in. Check your connection and try again.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Pick up where you left off."
      footer={
        <>
          New here?{' '}
          <Link to="/signup" className="font-semibold text-ink underline decoration-flag decoration-2 underline-offset-4">
            Create an account
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={submit} noValidate={false}>
        <label className="block">
          <span className="label">Email</span>
          <input type="email" required autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className="field mt-1.5" placeholder="you@business.com" />
        </label>
        <label className="block">
          <span className="label">Password</span>
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="field mt-1.5" />
        </label>

        {error && (
          <p role="alert" className="rounded-[3px] border border-fail/40 bg-fail-soft px-3.5 py-2.5 text-sm text-fail">
            {error}
          </p>
        )}

        <button type="submit" disabled={loading} className="btn btn-flag w-full py-3">
          {loading ? <><Spinner className="h-4 w-4" /> Signing in</> : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}
