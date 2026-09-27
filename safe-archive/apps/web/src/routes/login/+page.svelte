<script lang="ts">
  import type { ActionData, PageData } from './$types';

  let { form, data }: { form: ActionData; data: PageData } = $props();
</script>

<svelte:head>
  <title>Sign in | SAFE-ARCHIVE</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<main class="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
  <div class="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
    <a href="/" class="text-sm font-semibold tracking-[0.18em] text-slate-700">SAFE-ARCHIVE</a>
    <h1 class="mt-8 text-2xl font-semibold text-slate-900">Sign in</h1>
    <p class="mt-2 text-sm text-slate-600">Access is limited to authorized accounts.</p>
    {#if data.passwordChanged}<p class="mt-6 rounded-md bg-green-50 px-4 py-3 text-sm text-green-900" role="status">Password changed. Sign in again.</p>{/if}

    {#if form?.message}
      <p class="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{form.message}</p>
    {/if}

    <form method="POST" class="mt-6 space-y-5">
      <div>
        <label for="email" class="block text-sm font-medium text-slate-800">Email</label>
        <input id="email" name="email" type="email" autocomplete="username" required value={form?.email ?? ''} class="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700" />
      </div>
      <div>
        <label for="password" class="block text-sm font-medium text-slate-800">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required class="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700" />
      </div>
      <button type="submit" class="w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700">Sign in</button>
    </form>
  </div>
</main>
