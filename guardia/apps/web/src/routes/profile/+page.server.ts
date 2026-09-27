import { fail, redirect } from '@sveltejs/kit';
import { accessToken, apiRequest, clearAccessToken, requireAccount } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  event.setHeaders({ 'cache-control': 'no-store' });
  return { account: await requireAccount(event) };
};

export const actions: Actions = {
  changePassword: async (event) => {
    const form = await event.request.formData();
    const current_password = String(form.get('current_password') ?? '');
    const new_password = String(form.get('new_password') ?? '');
    const confirmation = String(form.get('confirmation') ?? '');
    if (new_password.length < 12 || new_password !== confirmation) return fail(400, { message: 'Use at least 12 characters and confirm the new password.' });
    const token = accessToken(event);
    if (!token) redirect(303, '/login');
    let response: Response;
    try {
      response = await apiRequest('/auth/change-password', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password, new_password })
      });
    } catch {
      return fail(503, { message: 'Password change is temporarily unavailable.' });
    }
    if (!response.ok) return fail(response.status, { message: response.status === 400 ? 'Current password is incorrect.' : 'Could not change the password.' });
    clearAccessToken(event);
    redirect(303, '/login?passwordChanged=1');
  },
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
