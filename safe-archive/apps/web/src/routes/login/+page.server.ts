import { fail, redirect } from '@sveltejs/kit';
import { apiRequest, setAccessToken } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = ({ url }) => ({ passwordChanged: url.searchParams.has('passwordChanged') });

export const actions: Actions = {
  default: async (event) => {
    const form = await event.request.formData();
    const email = String(form.get('email') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if (!email || !password) return fail(400, { message: 'Enter your email and password.', email });

    let response: Response;
    try {
      response = await apiRequest('/auth/token', {
        method: 'POST',
        body: new URLSearchParams({ username: email, password })
      });
    } catch {
      return fail(503, { message: 'Sign in is temporarily unavailable.', email });
    }

    if (response.status === 401) return fail(401, { message: 'Invalid email or password.', email });
    if (!response.ok) return fail(503, { message: 'Sign in is temporarily unavailable.', email });

    const token = (await response.json()) as { access_token: string; expires_in: number };
    setAccessToken(event, token.access_token, token.expires_in);
    redirect(303, '/cases');
  }
};
