<script lang="ts">
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();
</script>

<svelte:head>
  <title>Account | SAFE-ARCHIVE</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<main class="mx-auto max-w-2xl px-6 py-16 text-slate-900">
  <a href="/" class="text-sm font-semibold tracking-[0.18em] text-slate-700">SAFE-ARCHIVE</a>
  <h1 class="mt-10 text-3xl font-semibold">Your account</h1>
  <div class="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
    <dl class="space-y-4">
      <div>
        <dt class="text-sm text-slate-500">Email</dt>
        <dd class="mt-1 font-medium">{data.account.email}</dd>
      </div>
      <div>
        <dt class="text-sm text-slate-500">Role</dt>
        <dd class="mt-1 font-medium capitalize">{data.account.role.replaceAll('_', ' ')}</dd>
      </div>
    </dl>
  </div>
  {#if form?.message}
    <p class="mt-6 text-sm text-red-800" role="alert">{form.message}</p>
  {/if}
  <form method="POST" action="?/logout" class="mt-8">
    <button type="submit" class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700">Sign out</button>
  </form>
</main>
