import { AxiosError, AxiosHeaders } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'
import { api, TOKEN_KEY } from './client'

describe('API authentication handling', () => {
  beforeEach(() => sessionStorage.clear())

  it('clears the session token and leaves a login notice after a 401', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'expired-session-token')

    await expect(api.get('/expired', {
      adapter: async (config) => {
        throw new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, undefined, {
          config,
          data: { detail: 'Access token expired' },
          headers: new AxiosHeaders(),
          status: 401,
          statusText: 'Unauthorized',
        })
      },
    })).rejects.toBeInstanceOf(AxiosError)

    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(sessionStorage.getItem('collabtrace_auth_notice')).toBe('登录状态已失效，请重新登录。')
  })
})
