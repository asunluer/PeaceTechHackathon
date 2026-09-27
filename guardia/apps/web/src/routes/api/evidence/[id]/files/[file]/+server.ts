import { error } from '@sveltejs/kit';
import { authorizedRequest, requireAccount } from '$lib/server/auth';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async (event) => {
  await requireAccount(event);
  const response = await authorizedRequest(event, `/evidence/${event.params.id}/files/${event.params.file}`, { signal: AbortSignal.timeout(60000) });
  if (!response.ok) error(response.status, 'Evidence file unavailable.');
  const contentType = response.headers.get('content-type') || 'application/octet-stream';
  const wantsPreview = event.url.searchParams.get('preview') === '1';
  const isImage = contentType === 'image/png';
  const isHtml = contentType.startsWith('text/html');
  const preview = wantsPreview && (isImage || isHtml);
  const headers: Record<string, string> = {
    'Content-Type': contentType,
    'Content-Disposition': preview ? `inline; filename="evidence-preview.${isHtml ? 'html' : 'png'}"` : response.headers.get('content-disposition') || 'attachment',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  };
  // Captured HTML is untrusted third-party content: never let it run script, read cookies, or navigate the top frame.
  if (isHtml) headers['Content-Security-Policy'] = "sandbox; default-src 'none'";
  return new Response(response.body, { headers });
};
