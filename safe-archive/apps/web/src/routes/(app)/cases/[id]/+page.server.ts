import { error, fail, redirect } from '@sveltejs/kit';
import { authorizedRequest, requireAccount } from '$lib/server/auth';
import type { Analysis, Audit, Case, CaseNote, Evidence, EvidenceFile, SubmittedLink, TimelineEvent } from '$lib/types';
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
  const analyses: Record<string, Analysis[]> = {};
  await Promise.all(evidence.map(async (item) => {
    [files[item.id], analyses[item.id]] = await Promise.all([
      read<EvidenceFile[]>(event, `/evidence/${item.id}/files`),
      account.role === 'victim' ? Promise.resolve([]) : read<Analysis[]>(event, `/evidence/${item.id}/analyses`)
    ]);
  }));
  const notes = account.role === 'victim' ? [] : await read<CaseNote[]>(event, `/cases/${id}/notes`);
  const audit = account.role === 'victim' ? [] : await read<Audit[]>(event, `/cases/${id}/audit`);
  const users: { id: string; email: string; role: string; is_active: boolean }[] = [];
  if (account.role === 'administrator') {
    for (let offset = 0; ; offset += 100) {
      const batch = await read<typeof users>(event, `/users?role=ngo_investigator&active=true&limit=100&offset=${offset}`);
      users.push(...batch);
      if (batch.length < 100) break;
    }
  }
  return { caseRecord, evidence, files, analyses, timeline, links, notes, audit, users, evidencePage, hasMoreEvidence };
};

export const actions: Actions = {
  addLink: async (event) => {
    const form = await event.request.formData();
    const url = String(form.get('url') ?? '').trim();
    if (!/^https?:\/\//i.test(url)) return fail(400, { message: 'Enter a public HTTP(S) link.' });
    const response = await authorizedRequest(event, `/cases/${event.params.id}/links`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    if (!response.ok) return fail(response.status, { message: 'Could not add the link.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  update: async (event) => {
    const form = await event.request.formData();
    const title = String(form.get('title') ?? '').trim();
    const status = String(form.get('status') ?? '').trim();
    const victim_statement = String(form.get('victim_statement') ?? '').trim();
    const account = await requireAccount(event);
    const body = account.role === 'victim' ? { title, victim_statement } : { title, status };
    const response = await authorizedRequest(event, `/cases/${event.params.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!response.ok) return fail(response.status, { message: 'Could not update the case.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  assign: async (event) => {
    const form = await event.request.formData();
    const investigator_id = String(form.get('investigator_id') ?? '') || null;
    const response = await authorizedRequest(event, `/cases/${event.params.id}/assignment`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ investigator_id }) });
    if (!response.ok) return fail(response.status, { message: 'Could not assign the investigator.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  note: async (event) => {
    const form = await event.request.formData();
    const body = String(form.get('body') ?? '').trim();
    const response = await authorizedRequest(event, `/cases/${event.params.id}/notes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body }) });
    if (!response.ok) return fail(response.status, { message: 'Could not add the note.' });
    redirect(303, `/cases/${event.params.id}`);
  },
  analyze: async (event) => {
    const form = await event.request.formData();
    const evidenceId = String(form.get('evidence_id') ?? '');
    if (!/^[0-9a-f-]{36}$/i.test(evidenceId)) return fail(400, { message: 'Invalid evidence item.' });
    const response = await authorizedRequest(event, `/evidence/${evidenceId}/analyses`, { method: 'POST' });
    if (!response.ok) return fail(response.status, { message: response.status === 503 ? 'AI analysis is not configured.' : 'Could not analyze this evidence.' });
    redirect(303, `/cases/${event.params.id}#evidence-${evidenceId}`);
  },
  retry: async (event) => {
    const form = await event.request.formData();
    const evidenceId = String(form.get('evidence_id') ?? '');
    if (!/^[0-9a-f-]{36}$/i.test(evidenceId)) return fail(400, { message: 'Invalid evidence item.' });
    const response = await authorizedRequest(event, `/evidence/${evidenceId}/retry`, { method: 'POST' });
    if (!response.ok) return fail(response.status, { message: 'Could not queue another capture attempt.' });
    redirect(303, `/cases/${event.params.id}#evidence-${evidenceId}`);
  }
};
