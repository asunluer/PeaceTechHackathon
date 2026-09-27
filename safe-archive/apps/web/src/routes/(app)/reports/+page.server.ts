import { error, redirect } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const { account } = await event.parent();
  if (account.role === 'victim') redirect(303, '/cases');
  const response = await authorizedRequest(event, '/cases?limit=100');
  if (!response.ok) error(response.status, 'Reports are unavailable.');
  return { cases: (await response.json()) as Case[] };
};
