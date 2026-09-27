import { error, fail, redirect } from '@sveltejs/kit';
import { authorizedRequest, requireAccount } from '$lib/server/auth';
import type { Audit, Case, CaseNote, Evidence, EvidenceFile, SubmittedLink, TimelineEvent } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

async function read<T>(event: Parameters<PageServerLoad>[0], path: string): Promise<T> {
  const response = await authorizedRequest(event, path);
  if (response.status === 404) error(404, 'Case not found.');
  if (!response.ok) error(response.status, 'Case data is unavailable.');
  return (await response.json()) as T;
}

export const load: PageServerLoad = async (event) => {
  const id = event.params.id;
  const { account } = await event.parent();
  const rawPage = Number(event.url.searchParams.get('evidencePage') ?? '1');
  const evidencePage = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const evidenceOffset = (evidencePage - 1) * 50;
  const caseRecord = await read<Case>(event, `/cases/${id}`);
  const [evidenceBatch, timeline] = await Promise.all([
    read<Evidence[]>(event, `/cases/${id}/evidence?limit=51&offset=${evidenceOffset}`),
    read<TimelineEvent[]>(event, `/cases/${id}/timeline`),
  ]);
  const evidence = evidenceBatch.slice(0, 50);
  const hasMoreEvidence = evidenceBatch.length > 50;
  const links: SubmittedLink[] = [];
  for (let offset = 0; ; offset += 100) {
    const batch = await read<SubmittedLink[]>(event, `/cases/${id}/links?limit=100&offset=${offset}`);
    links.push(...batch);
    if (batch.length < 100) break;
  }
  const files: Record<string, EvidenceFile[]> = {};
  await Promise.all(evidence.map(async (item) => {
    files[item.id] = await read<EvidenceFile[]>(event, `/evidence/${item.id}/files`);
  }));
  const [notes, audit, contact] = await Promise.all([
    read<CaseNote[]>(event, `/cases/${id}/notes`),
    read<Audit[]>(event, `/cases/${id}/audit`),
    read<{ email: string }>(event, `/cases/${id}/contact`),
  ]);
  const users: { id: string; email: string; role: string; is_active: boolean }[] = [];
  if (account.role === 'administrator') {
    for (let offset = 0; ; offset += 100) {
      const batch = await read<typeof users>(event, `/users?role=ngo_investigator&active=true&limit=100&offset=${offset}`);
      users.push(...batch);
      if (batch.length < 100) break;
    }
  }
  return { caseRecord, evidence, files, timeline, links, notes, audit, contact, users, evidencePage, hasMoreEvidence };
};

// Form actions do not run the layout load, so each one re-checks that the session belongs to NGO staff.
export const actions: Actions = {
  update: async (event) => {
    await requireAccount(event);
    const form = await event.request.formData();
    const title = String(form.get('title') ?? '').trim();
    const status = String(form.get('status') ?? '').trim();
    const response = await authorizedRequest(event, `/cases/${event.params.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, status }) });
    if (!response.ok) return fail(response.status, { message: 'Could not update the case.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  assign: async (event) => {
    await requireAccount(event);
    const form = await event.request.formData();
    const investigator_id = String(form.get('investigator_id') ?? '') || null;
    const response = await authorizedRequest(event, `/cases/${event.params.id}/assignment`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ investigator_id }) });
    if (!response.ok) return fail(response.status, { message: 'Could not assign the investigator.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  note: async (event) => {
    await requireAccount(event);
    const form = await event.request.formData();
    const body = String(form.get('body') ?? '').trim();
    const response = await authorizedRequest(event, `/cases/${event.params.id}/notes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body }) });
    if (!response.ok) return fail(response.status, { message: 'Could not add the note.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  retry: async (event) => {
    await requireAccount(event);
    const form = await event.request.formData();
    const evidenceId = String(form.get('evidence_id') ?? '');
    if (!/^[0-9a-f-]{36}$/i.test(evidenceId)) return fail(400, { message: 'Invalid evidence item.' });
    const response = await authorizedRequest(event, `/evidence/${evidenceId}/retry`, { method: 'POST' });
    if (!response.ok) return fail(response.status, { message: 'Could not queue another capture attempt.' });
    redirect(303, `/cases/${event.params.id}#evidence-${evidenceId}`);
  }
};
