import { env } from '$env/dynamic/private';
import { error, redirect, type RequestEvent } from '@sveltejs/kit';

const ACCESS_COOKIE = 'guardia_access';

export type Account = {
  id: string;
  email: string;
  role: 'victim' | 'ngo_investigator' | 'administrator';
  is_active: boolean;
  created_at: string;
};

export function accessToken(event: RequestEvent): string | undefined {
  return event.cookies.get(ACCESS_COOKIE);
}

export function setAccessToken(event: RequestEvent, token: string, expiresIn: number): void {
  event.cookies.set(ACCESS_COOKIE, token, {
    path: '/',
    httpOnly: true,
    sameSite: 'strict',
    secure: event.url.protocol === 'https:',
    maxAge: expiresIn
  });
}

export function clearAccessToken(event: RequestEvent): void {
  event.cookies.delete(ACCESS_COOKIE, { path: '/' });
}

export async function apiRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const baseUrl = (env.API_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  return fetch(`${baseUrl}/api/v1${path}`, {
    ...init,
    cache: 'no-store',
    signal: init.signal ?? AbortSignal.timeout(10000)
  });
}

export async function authorizedRequest(event: RequestEvent, path: string, init: RequestInit = {}): Promise<Response> {
  const token = accessToken(event);
  if (!token) redirect(303, '/login');
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${token}`);
  return apiRequest(path, { ...init, headers });
}

export async function requireAccount(event: RequestEvent): Promise<Account> {
  const token = accessToken(event);
  if (!token) redirect(303, '/login');

  let response: Response;
  try {
    response = await apiRequest('/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    error(503, 'The authentication service is unavailable.');
  }

  if (response.status === 401) {
    clearAccessToken(event);
    redirect(303, '/login');
  }
  if (!response.ok) error(503, 'The authentication service is unavailable.');
  const account = (await response.json()) as Account;
  // The web workspace is for NGO staff only; victims report through the mobile app.
  if (account.role === 'victim') {
    clearAccessToken(event);
    redirect(303, '/login?staffOnly=1');
  }
  return account;
}
