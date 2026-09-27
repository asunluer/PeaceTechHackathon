<script lang="ts">
  import { page } from '$app/state';

  let { data, children } = $props();
  const links = [
    { href: '/dashboard', label: 'Dashboard', roles: ['ngo_investigator', 'administrator'] },
    { href: '/cases', label: 'Cases', roles: ['ngo_investigator', 'administrator'] },
    { href: '/reports', label: 'Reports', roles: ['ngo_investigator', 'administrator'] },
    { href: '/settings', label: 'Users', roles: ['administrator'] },
    { href: '/profile', label: 'Profile', roles: ['ngo_investigator', 'administrator'] }
  ];
</script>

<div class="min-h-screen bg-slate-50 text-slate-900 lg:flex">
  <aside class="border-b border-slate-200 bg-slate-900 text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:flex-col lg:border-b-0">
    <div class="border-b border-white/10 px-6 py-6">
      <a href="/dashboard" class="flex items-center gap-3">
        <span class="flex size-10 items-center justify-center rounded-lg bg-white text-sm font-bold text-slate-900">G</span>
        <span class="text-sm font-semibold tracking-[0.16em]">GUARDIA</span>
      </a>
      <p class="mt-4 text-xs leading-5 text-slate-300">Public evidence preservation workspace</p>
    </div>
    <nav aria-label="Main navigation" class="flex gap-1 overflow-x-auto px-3 py-3 lg:flex-col lg:gap-1 lg:py-6">
      {#each links.filter((link) => link.roles.includes(data.account.role)) as link}
        <a
          href={link.href}
          aria-current={page.url.pathname === link.href || page.url.pathname.startsWith(link.href + '/') ? 'page' : undefined}
          class="whitespace-nowrap rounded-lg px-4 py-2.5 text-sm font-medium transition hover:bg-white/10 aria-[current=page]:bg-white/15 aria-[current=page]:text-white"
        >{link.label}</a>
      {/each}
    </nav>
    <div class="hidden border-t border-white/10 px-6 py-5 text-xs text-slate-300 lg:mt-auto lg:block">
      <div class="truncate font-medium text-white">{data.account.email}</div>
      <div class="mt-1 capitalize">{data.account.role.replaceAll('_', ' ')}</div>
    </div>
  </aside>
  <div class="min-w-0 flex-1">
    <header class="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4 lg:px-10">
      <span class="text-sm font-medium text-slate-600">Evidence workspace</span>
      <a href="/profile" class="text-sm font-medium text-slate-700 underline-offset-4 hover:underline">Account</a>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-8 lg:px-10 lg:py-10">
      {@render children()}
    </main>
  </div>
</div>
