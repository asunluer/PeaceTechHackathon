import { error } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const [casesResponse, statsResponse] = await Promise.all([
    authorizedRequest(event, '/cases?limit=8'),
    authorizedRequest(event, '/cases/stats')
  ]);
  if (!casesResponse.ok || !statsResponse.ok) error(503, 'Cases are temporarily unavailable.');
  const cases = (await casesResponse.json()) as Case[];
  const stats = (await statsResponse.json()) as { total: number; open: number; in_review: number };
  return { cases, stats };
};
