import { message } from 'antd'
import { client } from '@/client/client.gen'
import { formatApiError } from '@/utils/errors'
import { getAuthToken, useAuthStore } from '@/stores/authStore'

client.setConfig({
  baseUrl: '',
  throwOnError: true,
})

client.interceptors.request.use((request) => {
  const token = getAuthToken()
  if (token && !request.headers.has('Authorization')) {
    request.headers.set('Authorization', `Bearer ${token}`)
  }
  return request
})

let redirectingToLogin = false

client.interceptors.response.use(async (response) => {
  if (response.status === 401) {
    useAuthStore.getState().logout()

    if (!redirectingToLogin && window.location.pathname !== '/login') {
      redirectingToLogin = true
      const back = window.location.pathname + window.location.search
      window.location.replace(`/login?back=${encodeURIComponent(back)}`)
    }
    if (window.location.pathname !== '/login') {
      message.error(await formatApiError(response))
    }
    return response
  }

  if (!response.ok) {
    message.error(await formatApiError(response))
  }
  return response
})
