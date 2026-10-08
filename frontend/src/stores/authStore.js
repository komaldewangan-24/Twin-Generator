import { create } from 'zustand'
import api from '../lib/api'

export const useAuthStore = create((set) => ({
  token: localStorage.getItem('token') || null,

  setToken: (token) => {
    localStorage.setItem('token', token)
    set({ token })
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null })
  },

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    useAuthStore.getState().setToken(data.access_token)
  },

  signup: async (email, password) => {
    const { data } = await api.post('/auth/signup', { email, password })
    useAuthStore.getState().setToken(data.access_token)
  },
}))