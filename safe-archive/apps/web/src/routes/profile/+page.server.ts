import { fail, redirect } from '@sveltejs/kit';
import { accessToken, apiRequest, clearAccessToken, requireAccount } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  event.setHeaders({ 'cache-control': 'no-store' });
  return { account: await requireAccount(event) };
};

export const actions: Actions = {
  logout: async (event) => {
    const token = accessToken(event);
    if (token) {
      try {
        const response = await apiRequest('/auth/logout', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok && response.status !== 401) {
          return fail(503, { message: 'Could not end the session. Please try again.' });
        }
      } catch {
        return fail(503, { message: 'Could not end the session. Please try again.' });
      }
    }
    clearAccessToken(event);
    redirect(303, '/login');
  }
};
