import { fail, redirect } from '@sveltejs/kit';
import { apiRequest, setAccessToken, type Account } from '$lib/server/auth';
import type { Actions, PageServerLoad } from './$types';

const STAFF_ONLY_MESSAGE = 'This workspace is for NGO staff only. To report content, use the GUARDIA mobile app.';

export const load: PageServerLoad = ({ url }) => ({
  passwordChanged: url.searchParams.has('passwordChanged'),
  staffOnly: url.searchParams.has('staffOnly') ? STAFF_ONLY_MESSAGE : null
});

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
    const authorization = { Authorization: `Bearer ${token.access_token}` };
    let account: Account;
    try {
      const me = await apiRequest('/auth/me', { headers: authorization });
      if (!me.ok) return fail(503, { message: 'Sign in is temporarily unavailable.', email });
      account = (await me.json()) as Account;
    } catch {
      return fail(503, { message: 'Sign in is temporarily unavailable.', email });
    }
    if (account.role === 'victim') {
      // Discard the token without calling /auth/logout: that revokes every token of the user,
      // which would also sign the victim out of the mobile app. This token never reaches the browser.
      return fail(403, { message: STAFF_ONLY_MESSAGE, email });
    }
    setAccessToken(event, token.access_token, token.expires_in);
    redirect(303, '/cases');
  }
};
