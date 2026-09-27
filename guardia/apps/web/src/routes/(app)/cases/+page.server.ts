import { error, fail, redirect } from '@sveltejs/kit';
import { authorizedRequest, requireAccount } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

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

export const actions: Actions = {
  submit: async (event) => {
    const account = await requireAccount(event);
    if (account.role !== 'victim') return fail(403, { message: 'Only victim accounts can submit reports.' });
    const form = await event.request.formData();
    const url = String(form.get('url') ?? '').trim();
    const victim_statement = String(form.get('victim_statement') ?? '').trim();
    const shared_text = String(form.get('shared_text') ?? '').trim();
    if (!/^https?:\/\//i.test(url)) return fail(400, { message: 'Enter a public HTTP(S) link.' });
    let response: Response;
    try {
      response = await authorizedRequest(event, '/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, victim_statement: victim_statement || null, shared_text: shared_text || null })
      });
    } catch {
      return fail(503, { message: 'Submission is temporarily unavailable.' });
    }
    if (!response.ok) return fail(response.status, { message: 'Could not submit this link. Check the URL and try again.' });
    const receipt = (await response.json()) as { case_id: string; evidence_id: string };
    redirect(303, `/cases/${receipt.case_id}?submitted=${receipt.evidence_id}`);
  }
};
