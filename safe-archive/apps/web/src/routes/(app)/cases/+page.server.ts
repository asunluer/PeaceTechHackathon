import { error, fail, redirect } from '@sveltejs/kit';
import { authorizedRequest, requireAccount } from '$lib/server/auth';
import type { Case } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async (event) => {
  const q = event.url.searchParams.get('q')?.trim() ?? '';
  const path = q ? `/cases?limit=100&q=${encodeURIComponent(q)}` : '/cases?limit=100';
  const response = await authorizedRequest(event, path);
  if (!response.ok) error(503, 'Cases are temporarily unavailable.');
  return { cases: (await response.json()) as Case[], query: q };
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
