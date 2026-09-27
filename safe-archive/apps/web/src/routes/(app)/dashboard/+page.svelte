<script lang="ts">
  let { data } = $props();
  const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
</script>

<svelte:head>
  <title>Dashboard | SAFE-ARCHIVE</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <p class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Investigator workspace</p>
    <h1 class="mt-2 text-3xl font-semibold tracking-tight">Dashboard</h1>
    <p class="mt-2 text-sm text-slate-600">Review submitted public links and preservation progress.</p>
  </div>
  <a href="/cases" class="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700">View all cases</a>
</div>

<div class="mt-8 grid gap-4 sm:grid-cols-3">
  <div class="rounded-xl border border-slate-200 bg-white p-6"><p class="text-sm text-slate-500">Visible cases</p><p class="mt-3 text-3xl font-semibold">{data.cases.length}</p></div>
  <div class="rounded-xl border border-slate-200 bg-white p-6"><p class="text-sm text-slate-500">In review</p><p class="mt-3 text-3xl font-semibold">{data.cases.filter((item) => item.status === 'in_review').length}</p></div>
  <div class="rounded-xl border border-slate-200 bg-white p-6"><p class="text-sm text-slate-500">Open</p><p class="mt-3 text-3xl font-semibold">{data.cases.filter((item) => item.status === 'open').length}</p></div>
</div>

<section class="mt-10 rounded-xl border border-slate-200 bg-white">
  <div class="border-b border-slate-200 px-6 py-5"><h2 class="text-lg font-semibold">Recent cases</h2></div>
  {#if data.cases.length === 0}
    <p class="px-6 py-10 text-sm text-slate-600">No cases are assigned to you yet.</p>
  {:else}
    <ul class="divide-y divide-slate-100">
      {#each data.cases.slice(0, 8) as item}
        <li><a href={`/cases/${item.id}`} class="flex flex-wrap items-center justify-between gap-3 px-6 py-4 hover:bg-slate-50"><span><span class="font-medium">{item.title}</span><span class="mt-1 block text-xs text-slate-500">{date(item.created_at)} · {item.id}</span></span><span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium capitalize text-slate-700">{item.status.replaceAll('_', ' ')}</span></a></li>
      {/each}
    </ul>
  {/if}
</section>
