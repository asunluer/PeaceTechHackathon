import { requireAccount } from '$lib/server/auth';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async (event) => {
  event.setHeaders({ 'cache-control': 'no-store' });
  return { account: await requireAccount(event) };
};
