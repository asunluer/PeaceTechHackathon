import { error, fail, redirect } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { Account } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const { account } = await event.parent();
  if (account.role !== 'administrator') redirect(303, '/dashboard');
  const response = await authorizedRequest(event, '/users');
  if (!response.ok) error(response.status, 'User list is unavailable.');
  return { users: (await response.json()) as Account[] };
};

export const actions: Actions = {
  create: async (event) => {
    const form = await event.request.formData();
    const response = await authorizedRequest(event, '/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: String(form.get('email') ?? ''), password: String(form.get('password') ?? ''), role: String(form.get('role') ?? '') }) });
    if (!response.ok) return fail(response.status, { message: response.status === 409 ? 'Email already exists.' : 'Could not create user.' });
    redirect(303, '/settings');
  },
  update: async (event) => {
    const form = await event.request.formData();
    const id = String(form.get('id') ?? '');
    if (!/^[0-9a-f-]{36}$/i.test(id)) return fail(400, { message: 'Invalid user.' });
    const response = await authorizedRequest(event, `/users/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: String(form.get('role') ?? ''), is_active: form.get('is_active') === 'on' }) });
    if (!response.ok) return fail(response.status, { message: 'Could not update user. The last active administrator must remain.' });
    redirect(303, '/settings');
  }
};
