import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import { Spinner } from '../components/ui'
import { apiErrorMessage } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const signup = useAuthStore((s) => s.signup)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('The two passwords are different. Type them again.')
      return
    }
    setLoading(true)
    try {
      await signup(email.trim().toLowerCase(), password)
      navigate('/')
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the account. Check your connection and try again.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="It takes a minute. Your first scan is a video away."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-ink underline decoration-flag decoration-2 underline-offset-4">
            Sign in
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={submit}>
        <label className="block">
          <span className="label">Email</span>
          <input type="email" required autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className="field mt-1.5" placeholder="you@business.com" />
        </label>
        <label className="block">
          <span className="label">Password · at least 6 characters</span>
          <input type="password" required minLength={6} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className="field mt-1.5" />
        </label>
        <label className="block">
          <span className="label">Confirm password</span>
          <input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="field mt-1.5" />
        </label>

        {error && (
          <p role="alert" className="rounded-[3px] border border-fail/40 bg-fail-soft px-3.5 py-2.5 text-sm text-fail">
            {error}
          </p>
        )}

        <button type="submit" disabled={loading} className="btn btn-flag w-full py-3">
          {loading ? <><Spinner className="h-4 w-4" /> Creating account</> : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}
