import { error } from '@sveltejs/kit';
import { authorizedRequest } from '$lib/server/auth';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async (event) => {
  const response = await authorizedRequest(event, `/cases/${event.params.id}/report.pdf`, { signal: AbortSignal.timeout(60000) });
  if (!response.ok) error(response.status, 'Report unavailable.');
  return new Response(response.body, { headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': `attachment; filename="safe-archive-${event.params.id}.pdf"`, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' } });
};
