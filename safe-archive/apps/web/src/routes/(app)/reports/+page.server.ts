import { error, redirect } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const { account } = await event.parent();
  if (account.role === 'victim') redirect(303, '/cases');
  const rawPage = Number(event.url.searchParams.get('page') ?? '1');
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const response = await authorizedRequest(event, `/cases?limit=51&offset=${(page - 1) * 50}`);
  if (!response.ok) error(response.status, 'Reports are unavailable.');
  const batch = (await response.json()) as Case[];
  return { cases: batch.slice(0, 50), page, hasMore: batch.length > 50 };
};
