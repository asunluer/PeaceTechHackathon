import { error } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const q = event.url.searchParams.get('q')?.trim() ?? '';
  const rawPage = Number(event.url.searchParams.get('page') ?? '1');
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const path = `/cases?limit=51&offset=${(page - 1) * 50}${q ? `&q=${encodeURIComponent(q)}` : ''}`;
  const response = await authorizedRequest(event, path);
  if (!response.ok) error(503, 'Cases are temporarily unavailable.');
  const batch = (await response.json()) as Case[];
  return { cases: batch.slice(0, 50), query: q, page, hasMore: batch.length > 50 };
};
