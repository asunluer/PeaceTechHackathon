<script lang="ts">
  let { data, form } = $props();
  const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
</script>

<svelte:head>
  <title>Cases | SAFE-ARCHIVE</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<div class="flex flex-wrap items-end justify-between gap-4">
  <div>
    <p class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Case management</p>
    <h1 class="mt-2 text-3xl font-semibold tracking-tight">Cases</h1>
    <p class="mt-2 text-sm text-slate-600">Your accessible reports and preservation records.</p>
  </div>
  <span class="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700">{data.cases.length} visible</span>
</div>

<form method="GET" class="mt-6 flex gap-2">
  <label class="sr-only" for="case-search">Search cases</label>
  <input
    id="case-search"
    name="q"
    type="search"
    maxlength="200"
    value={data.query}
    placeholder="Search titles, statements, captured text, tags…"
    class="w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm"
  />
  <button type="submit" class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">Search</button>
  {#if data.query}<a href="/cases" class="rounded-md px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900">Clear</a>{/if}
</form>

{#if data.account.role === 'victim'}
  <section class="mt-8 rounded-xl border border-slate-200 bg-white p-6">
    <h2 class="text-lg font-semibold">Submit a public link</h2>
    <p class="mt-2 text-sm text-slate-600">We preserve only content publicly visible at the link. Do not include passwords or private messages.</p>
    {#if form?.message}<p class="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800" role="alert">{form.message}</p>{/if}
    <form method="POST" action="?/submit" class="mt-5 grid gap-4">
      <label class="grid gap-1 text-sm font-medium">Public URL<input name="url" type="url" required maxlength="2048" placeholder="https://example.org/post" class="rounded-md border border-slate-300 px-3 py-2 font-normal" /></label>
      <label class="grid gap-1 text-sm font-medium">What happened? <span class="font-normal text-slate-500">Optional</span><textarea name="victim_statement" rows="3" maxlength="4000" class="rounded-md border border-slate-300 px-3 py-2 font-normal"></textarea></label>
      <button type="submit" class="w-fit rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700">Submit for preservation</button>
    </form>
  </section>
{/if}

<section class="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white">
  {#if data.cases.length === 0}
    <p class="p-8 text-sm text-slate-600">{data.query ? `No cases match "${data.query}".` : 'No cases to show.'}</p>
  {:else}
    <ul class="divide-y divide-slate-100">
      {#each data.cases as item}
        <li><a href={`/cases/${item.id}`} class="flex flex-wrap items-center justify-between gap-3 px-6 py-5 hover:bg-slate-50"><span><span class="font-semibold">{item.title}</span><span class="mt-1 block text-xs text-slate-500">Created {date(item.created_at)} · {item.id}</span></span><span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium capitalize text-slate-700">{item.status.replaceAll('_', ' ')}</span></a></li>
      {/each}
    </ul>
  {/if}
</section>
{#if data.page > 1 || data.hasMore}
  <nav aria-label="Case pages" class="mt-4 flex items-center gap-4 text-sm">
    {#if data.page > 1}<a class="font-medium text-blue-700 underline" href={`?page=${data.page - 1}${data.query ? `&q=${encodeURIComponent(data.query)}` : ''}`}>Previous</a>{/if}
    <span>Page {data.page}</span>
    {#if data.hasMore}<a class="font-medium text-blue-700 underline" href={`?page=${data.page + 1}${data.query ? `&q=${encodeURIComponent(data.query)}` : ''}`}>Next</a>{/if}
  </nav>
{/if}
